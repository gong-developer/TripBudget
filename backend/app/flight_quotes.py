"""Explicit, quota-bounded Google Flights searches via SerpApi, never bulk recommendations."""
import asyncio
from collections import OrderedDict
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import time
from urllib.parse import urlsplit

from fastapi import HTTPException
import httpx
from pydantic import ConfigDict, Field
from .costs import ALIASES, ORIGINS, TripOptions, distance, estimate
from .storage import database

CACHE=OrderedDict()
INFLIGHT={}
NO_RESULTS=OrderedDict()
TTL=600
log=logging.getLogger(__name__)
# httpx logs GET query strings at INFO, which would include the private API key.
class SecretFilter(logging.Filter):
    def filter(self, record):
        if 'serpapi.com/' in record.getMessage():
            record.msg=re.sub(r'(api_key=)[^&\s"\']+',r'\1[redacted]',record.getMessage())
            record.args=()
        return True
logging.getLogger('httpx').addFilter(SecretFilter())


class FlightSearchRequest(TripOptions):
    model_config=ConfigDict(extra='forbid')
    cityName: str=Field(min_length=1,max_length=200)
    departureAirport: str=Field(pattern='^[A-Z]{3}$')
    arrivalAirport: str=Field(pattern='^[A-Z]{3}$')
    departureDate: date=Field(le=date(2100,12,31))


@lru_cache(maxsize=1)
def airports():
    data=json.loads((Path(__file__).resolve().parents[1]/'data/flight-airports.json').read_text())
    return {row['code']:row for row in data['airports']}


def country_code(city):
    return 'kr' if city['category']=='domestic' else city.get('countryCode') or next((code for name,code in ALIASES.items() if name in city['cityName']),'')


def airport_options(city,origin):
    def near(rows,lat,lng):
        return sorted(({**row,'distanceKm':round(distance(lat,lng,row['lat'],row['lng']))} for row in rows),key=lambda row:row['distanceKm'])
    _,lat,lng=ORIGINS[origin]
    departure=near([row for row in airports().values() if row['countryCode']=='kr'],lat,lng)
    arrival=near([row for row in airports().values() if row['countryCode']==country_code(city)],city['lat'],city['lng'])[:12]
    default_departure=departure[0]['code'] if departure else ''
    if city['category']=='international' and origin in ('seoul','incheon','gyeonggi') and 'ICN' in airports():
        default_departure='ICN'
    return {'configured':bool(os.getenv('SERPAPI_API_KEY','').strip()),'departureAirports':departure,'arrivalAirports':arrival,
            'departureDefault':default_departure,
            'arrivalDefault':arrival[0]['code'] if arrival and arrival[0]['distanceKm']<=300 else '',
            'monthlyLimit':monthly_limit(),'requestsPerSearch':2,'source':'OurAirports'}


def monthly_limit():
    try:return max(0,int(os.getenv('SERPAPI_MONTHLY_SEARCH_LIMIT','200')))
    except ValueError:return 200


def reserve_search():
    # Persistent app-wide counter, including failed requests that may have consumed credits.
    now=datetime.now(timezone.utc);key=f'flight-month:{now:%Y-%m}'
    with database('API_LIMIT_DB','api-limits.sqlite3') as db:
        db.execute('CREATE TABLE IF NOT EXISTS counters (key TEXT PRIMARY KEY, count INTEGER NOT NULL, expires REAL NOT NULL)')
        db.execute('BEGIN IMMEDIATE')
        count=db.execute('SELECT count FROM counters WHERE key=?',(key,)).fetchone()
        if (count[0] if count else 0)>=monthly_limit():
            raise HTTPException(429,'앱에 설정된 이번 달 항공권 조회 한도에 도달했어요. 예상 경비 또는 직접 입력한 항공료를 사용해주세요.')
        next_month=(now.replace(day=28)+timedelta(days=4)).replace(day=1,hour=0,minute=0,second=0,microsecond=0)
        db.execute('INSERT INTO counters(key,count,expires) VALUES (?,1,?) ON CONFLICT(key) DO UPDATE SET count=count+1',(key,next_month.timestamp()))


async def provider_search(params):
    key=os.getenv('SERPAPI_API_KEY','').strip()
    if not key:raise HTTPException(503,'항공권 조회를 사용하려면 서버에 SERPAPI_API_KEY를 설정해주세요.')
    lookup_key=(hashlib.sha256(key.encode()).digest(),tuple(sorted((name,str(value)) for name,value in params.items())))
    cached=NO_RESULTS.get(lookup_key)
    if cached and cached[0]>time.monotonic():raise HTTPException(404,cached[1])
    if cached:NO_RESULTS.pop(lookup_key,None)
    reserve_search()
    try:
        async with httpx.AsyncClient(timeout=25,follow_redirects=False) as client:
            response=await client.get('https://serpapi.com/search.json',params={**params,'api_key':key})
        if response.status_code in (401,403):
            raise HTTPException(503,'항공권 API 인증에 실패했어요. 서버의 SerpApi 키와 이용 상태를 확인해주세요.')
        if response.status_code==429:
            raise HTTPException(429,'SerpApi 항공권 조회 한도에 도달했어요. 잠시 후 다시 시도하거나 이용 한도를 확인해주세요.')
        if response.status_code>=400:raise HTTPException(502,'항공권 제공자가 조회를 완료하지 못했어요. 잠시 후 다시 시도해주세요.')
        data=response.json()
        if not isinstance(data,dict):raise HTTPException(502,'항공권 검색 응답 형식이 올바르지 않아요. 잠시 후 다시 시도해주세요.')
        metadata=data.get('search_metadata')
        if not isinstance(metadata,dict):raise HTTPException(502,'항공권 검색 응답 형식이 올바르지 않아요. 잠시 후 다시 시도해주세요.')
        error=data.get('error')
        # SerpApi uses HTTP 200 + Success + an error string for a genuine empty search.
        # Do not treat these as provider failures, or hide outages as missing flights.
        if (metadata.get('status')=='Success' and isinstance(error,str)
                and re.fullmatch(r"Google(?: Flights)? has(?:n't| not) returned any results for this query\.?",error.strip(),re.I)
                and not data.get('best_flights') and not data.get('other_flights')):
            leg='선택한 출국편에 맞는 귀국편' if params.get('departure_token') else '왕복 항공권'
            detail=(f"{params['departure_id']} ↔ {params['arrival_id']} · {params['outbound_date']}~{params['return_date']} "
                    f"조건에서 {leg} 검색 결과가 없어요. 실제 항공편이 없다는 뜻은 아닙니다. "
                    '출발·도착 공항이나 날짜·여행 기간을 바꿔 확인해주세요.')
            NO_RESULTS[lookup_key]=(time.monotonic()+120,detail);NO_RESULTS.move_to_end(lookup_key)
            while len(NO_RESULTS)>128:NO_RESULTS.popitem(last=False)
            raise HTTPException(404,detail)
        if error or metadata.get('status')!='Success':
            search_id=str(metadata.get('id') or '')
            safe_id=search_id if re.fullmatch('[A-Za-z0-9_-]{1,64}',search_id) else 'unknown'
            log.warning('Flight provider response unsuccessful search=%s',safe_id)
            raise HTTPException(502,'항공권 제공자가 검색 결과를 정상적으로 반환하지 못했어요. 잠시 후 다시 시도해주세요. 기존 경비는 유지됩니다.')
        returned=data.get('search_parameters')
        if not isinstance(returned,dict):raise HTTPException(502,'항공권 검색 조건을 확인하지 못했어요.')
        if returned.get('currency')!='KRW' or int(returned.get('type',1))!=1:
            raise HTTPException(502,'왕복 원화 가격인지 확인할 수 없어 경비에 반영하지 않았어요.')
        for name in ('departure_id','arrival_id','outbound_date','return_date'):
            if returned.get(name)!=params[name]:raise HTTPException(502,'검색 조건이 일치하지 않아 항공료를 반영하지 않았어요.')
        if int(returned.get('adults',1))!=1:raise HTTPException(502,'1인 요금 여부를 확인할 수 없어 반영하지 않았어요.')
        return data
    except httpx.TimeoutException:
        raise HTTPException(504,'항공권 조회 시간이 초과됐어요. 자동 재시도는 하지 않았습니다. 잠시 후 다시 시도해주세요.') from None
    except (httpx.HTTPError,ValueError,TypeError):
        raise HTTPException(502,'항공권 검색 응답을 읽지 못했어요. 기존 예상 경비는 유지됩니다.') from None


def candidates(data,origin,destination,travel_date):
    result=[]
    rows=[]
    for field in ('best_flights','other_flights'):
        values=data.get(field) or []
        if not isinstance(values,list):raise HTTPException(502,'항공편 목록 형식이 올바르지 않아요.')
        rows.extend(values)
    for row in rows:
        try:
            price=row.get('price');segments=row['flights']
            if type(price) is not int or not 0<price<=20000000 or not segments:continue
            if segments[0]['departure_airport']['id']!=origin or segments[-1]['arrival_airport']['id']!=destination:continue
            if segments[0]['departure_airport']['time'][:10]!=travel_date:continue
            clean=[]
            for segment in segments:
                dep,arr=segment['departure_airport'],segment['arrival_airport']
                if not re.fullmatch('[A-Z]{3}',dep['id']) or not re.fullmatch('[A-Z]{3}',arr['id']):raise ValueError()
                clean.append({'departureAirport':dep['id'],'arrivalAirport':arr['id'],
                              'departureTime':str(dep['time'])[:30],'arrivalTime':str(arr['time'])[:30],
                              'airline':str(segment.get('airline') or '항공사 정보 미제공')[:100],
                              'flightNumber':str(segment.get('flight_number') or '')[:30]})
            result.append({'price':price,'segments':clean,'token':row.get('departure_token')})
        except (KeyError,TypeError,ValueError,IndexError,AttributeError):continue
    return sorted(result,key=lambda row:row['price'])


def search_url(raw):
    if isinstance(raw,str):
        try:parsed=urlsplit(raw)
        except ValueError:return 'https://www.google.com/travel/flights?hl=ko&curr=KRW'
        if parsed.scheme=='https' and parsed.netloc in ('www.google.com','google.com') and parsed.path.startswith('/travel/flights'):
            return raw
    return 'https://www.google.com/travel/flights?hl=ko&curr=KRW'


def validate_search(city,request):
    today=datetime.now(timezone(timedelta(hours=9))).date()
    if request.departureDate<today:raise HTTPException(422,'출발일은 오늘 이후로 선택해주세요.')
    if request.days<2:raise HTTPException(422,'왕복 항공권 조회는 2일 이상 여행에서 사용할 수 있어요.')
    end=request.departureDate+timedelta(days=request.days-1)
    if end.year>2100:raise HTTPException(422,'귀국일은 2100년 이내로 선택해주세요.')
    dep=airports().get(request.departureAirport);arr=airports().get(request.arrivalAirport)
    if not dep or dep['countryCode']!='kr':raise HTTPException(422,'대한민국의 출발 공항을 선택해주세요.')
    if not arr or not country_code(city) or arr['countryCode']!=country_code(city):raise HTTPException(422,'선택한 여행지와 같은 국가의 도착 공항을 선택해주세요.')
    if dep['code']==arr['code']:raise HTTPException(422,'출발 공항과 도착 공항을 다르게 선택해주세요.')
    return end


async def quote_for(city,request):
    end=validate_search(city,request)
    api_key=os.getenv('SERPAPI_API_KEY','').strip()
    if not api_key:raise HTTPException(503,'항공권 조회를 사용하려면 서버에 SERPAPI_API_KEY를 설정해주세요.')
    # A one-person search makes the fare unit unambiguous. Group totals remain estimates.
    params={'engine':'google_flights','departure_id':request.departureAirport,'arrival_id':request.arrivalAirport,
            'outbound_date':str(request.departureDate),'return_date':str(end),'type':1,
            'adults':1,'travel_class':1,'currency':'KRW','hl':'ko','gl':'kr','sort_by':2,'deep_search':'true'}
    cache_key=(hashlib.sha256(api_key.encode()).digest(),tuple(sorted(params.items())))
    now=time.monotonic()
    cached=CACHE.get(cache_key)
    if cached and cached[0]>now:return cached[1]
    if cached:CACHE.pop(cache_key,None)
    task=INFLIGHT.get(cache_key)
    if task is None:
        async def fetch():
            first=await provider_search(params)
            outbound=next((row for row in candidates(first,request.departureAirport,request.arrivalAirport,str(request.departureDate))
                           if isinstance(row['token'],str) and 0<len(row['token'])<=16000),None)
            if not outbound:raise HTTPException(404,'선택한 날짜·공항의 왕복 항공권을 찾지 못했어요. 공항이나 날짜를 바꿔주세요.')
            second=await provider_search({**params,'departure_token':outbound['token']})
            inbound=candidates(second,request.arrivalAirport,request.departureAirport,str(end))
            if not inbound:raise HTTPException(404,'귀국편까지 확인된 왕복 항공권을 찾지 못해 경비에 반영하지 않았어요.')
            selected=inbound[0]
            metadata=second.get('search_metadata') or {}
            quote={'source':'Google Flights · SerpApi','currency':'KRW','pricePerPerson':selected['price'],'searchedPeople':1,
                   'departureAirport':request.departureAirport,'arrivalAirport':request.arrivalAirport,
                   'departureDate':str(request.departureDate),'returnDate':str(end),
                   'outbound':outbound['segments'],'inbound':selected['segments'],
                   'queriedAt':datetime.now(timezone.utc).isoformat(),
                   'providerTimestamp':str(metadata.get('created_at') or '')[:40],
                   'searchUrl':search_url(metadata.get('google_flights_url')),
                   'arrivalDistanceKm':round(distance(city['lat'],city['lng'],airports()[request.arrivalAirport]['lat'],airports()[request.arrivalAirport]['lng']))}
            CACHE[cache_key]=(time.monotonic()+TTL,quote);CACHE.move_to_end(cache_key)
            while len(CACHE)>128:CACHE.popitem(last=False)
            return quote
        task=asyncio.create_task(fetch());INFLIGHT[cache_key]=task
        def finished(done):
            if INFLIGHT.get(cache_key) is done:INFLIGHT.pop(cache_key,None)
            if not done.cancelled():done.exception()
        task.add_done_callback(finished)
    return await asyncio.shield(task)


def quoted_cost(city,request,quote):
    options=request.model_copy(update={'transportPerPerson':quote['pricePerPerson']})
    cost=estimate(city,options)
    item=next(row for row in cost['items'] if row['key']=='transport')
    item.update(label='왕복 항공료 (1인 조회가 적용)',source=quote['source'],
                basis=f"1인 왕복 검색가 {quote['pricePerPerson']:,}원 × {request.people}명")
    cost['priceType']='mixed';cost['flightQuote']=quote
    cost['warnings'][0]='항공료는 1인 왕복 검색가를 반영했고, 숙박·식비 등 나머지 항목은 계획용 추정입니다. 예약 시 가격이 달라질 수 있습니다.'
    cost['warnings'].extend(['검색 결과 캐시가 사용될 수 있습니다(SerpApi 최대 1시간, 앱 최대 10분).',
                             '위탁 수하물·좌석 지정·결제 수수료와 공항↔여행지 이동비는 별도로 확인해주세요.'])
    if request.people>1:cost['warnings'].append('여러 명의 항공료는 1인 조회가를 인원수만큼 곱한 추정입니다. 전원 동일 요금·잔여 좌석은 확인하지 않았습니다.')
    cost['basis']+=' 항공료 항목만 선택한 공항·날짜의 1인 왕복 검색가로 교체했습니다.'
    return cost
