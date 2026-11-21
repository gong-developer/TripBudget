import asyncio
from datetime import datetime,timedelta,timezone
import logging
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app import flight_quotes as fq
from app.main import app,EXTERNAL_CITIES

REAL_HTTP_CLIENT=httpx.AsyncClient

TARGET={'cityName':'도쿄 · 일본','lat':35.68,'lng':139.69,'category':'international','countryCode':'jp',
        'estimatedCost':700000,'recommendedPlaces':[]}


def body(**changes):
    return {'cityName':TARGET['cityName'],'departureAirport':'ICN','arrivalAirport':'NRT',
            'departureDate':str((datetime.now(timezone.utc)+timedelta(days=30)).date()),'days':3,'people':3,
            'themes':['food','shopping'],**changes}


def response(params,returning=False,price=430000):
    dep,arr=('NRT','ICN') if returning else ('ICN','NRT')
    travel_date=params['return_date' if returning else 'outbound_date']
    row={'price':price,'flights':[{'departure_airport':{'id':dep,'time':travel_date+' 09:00'},
        'arrival_airport':{'id':arr,'time':travel_date+' 12:00'},'airline':'검증 항공사','flight_number':'TB 123'}]}
    if not returning:row['departure_token']='verified-outbound-token'
    return {'search_metadata':{'status':'Success','created_at':'2026-11-04 03:00:00 UTC',
             'google_flights_url':'https://www.google.com/travel/flights/search?tfs=verified'},
            'search_parameters':params,'best_flights':[row]}


@pytest.fixture
def provider(monkeypatch):
    EXTERNAL_CITIES[TARGET['cityName']]=TARGET
    monkeypatch.setenv('SERPAPI_API_KEY','private-flight-test-key')
    monkeypatch.setenv('SERPAPI_MONTHLY_SEARCH_LIMIT','200')
    calls=[]
    real_client=httpx.AsyncClient
    def handler(request):
        params=dict(request.url.params);calls.append(params)
        assert params.pop('api_key')=='private-flight-test-key'
        assert params['adults']=='1' and params['currency']=='KRW'
        return httpx.Response(200,json=response(params,'departure_token' in params))
    monkeypatch.setattr(fq.httpx,'AsyncClient',lambda **kwargs:real_client(transport=httpx.MockTransport(handler),**kwargs))
    return calls


def test_airports_are_local_and_options_never_search_flights(monkeypatch):
    EXTERNAL_CITIES[TARGET['cityName']]=TARGET
    forbidden=AsyncMock(side_effect=AssertionError('must not spend searches'))
    monkeypatch.setattr(fq,'provider_search',forbidden)
    reply=TestClient(app).get('/api/flights/options',params={'cityName':TARGET['cityName']})
    assert reply.status_code==200
    assert not reply.json()['configured']
    assert {'ICN','GMP'}<={row['code'] for row in reply.json()['departureAirports']}
    assert all(row['countryCode']=='jp' for row in reply.json()['arrivalAirports'])
    forbidden.assert_not_awaited()


def test_roundtrip_quote_replaces_transport_and_recomputes_buffer(provider):
    reply=TestClient(app).post('/api/flights/search',json=body())
    assert reply.status_code==200,reply.text
    data=reply.json();cost=data['costBreakdown'];quote=data['quote']
    assert len(provider)==2 and provider[1]['departure_token']=='verified-outbound-token'
    assert quote['outbound'][0]['departureAirport']=='ICN'
    assert quote['inbound'][0]['departureAirport']=='NRT'
    assert quote['pricePerPerson']==430000 and quote['searchedPeople']==1
    transport=next(item for item in cost['items'] if item['key']=='transport')
    assert transport['amount']==430000*3 and transport['source']=='Google Flights · SerpApi'
    assert transport['low']==transport['high']==transport['amount']
    subtotal=sum(item['amount'] for item in cost['items'] if item['key']!='buffer')
    assert next(item for item in cost['items'] if item['key']=='buffer')['amount']==round(subtotal*.1)
    assert cost['total']==subtotal+round(subtotal*.1) and cost['priceType']=='mixed'
    assert cost['flightQuote']['departureDate']==body()['departureDate']
    assert any('잔여 좌석' in message for message in cost['warnings'])
    assert 'private-flight-test-key' not in reply.text


def test_cache_and_inflight_requests_do_not_spend_extra_searches(provider):
    async def run():
        request=fq.FlightSearchRequest(**body())
        one,two=await asyncio.gather(fq.quote_for(TARGET,request),fq.quote_for(TARGET,request))
        assert one==two==await fq.quote_for(TARGET,request)
    asyncio.run(run())
    assert len(provider)==2
    # Changing group size reuses a one-person search, but recalculates the group total.
    response=TestClient(app).post('/api/flights/search',json=body(people=2))
    assert response.status_code==200 and len(provider)==2
    assert next(item for item in response.json()['costBreakdown']['items'] if item['key']=='transport')['amount']==860000


@pytest.mark.parametrize('change',[{'departureAirport':'XXX'},{'arrivalAirport':'JFK'},
    {'departureAirport':'NRT'},{'days':1},{'departureDate':'2000-01-01'},
    {'departureAirport':'ICN&api_key=bad'},{'people':0}])
def test_invalid_conditions_never_reach_provider(provider,change):
    response=TestClient(app).post('/api/flights/search',json=body(**change))
    assert response.status_code==422 and provider==[]


def test_missing_key_cannot_be_mistaken_for_a_live_price(monkeypatch):
    EXTERNAL_CITIES[TARGET['cityName']]=TARGET
    response=TestClient(app).post('/api/flights/search',json=body())
    assert response.status_code==503 and 'SERPAPI_API_KEY' in response.json()['detail']
    assert fq.CACHE=={}


def test_monthly_cap_persists_and_blocks_requests(provider,monkeypatch):
    monkeypatch.setenv('SERPAPI_MONTHLY_SEARCH_LIMIT','2')
    client=TestClient(app)
    assert client.post('/api/flights/search',json=body()).status_code==200
    assert client.post('/api/flights/search',json=body(days=4)).status_code==429
    assert len(provider)==2
    assert client.post('/api/flights/search',json=body()).status_code==200 # cached
    assert len(provider)==2


def test_no_return_leg_is_never_applied(provider,monkeypatch):
    async def search(params):
        if 'departure_token' in params:return {'best_flights':[]}
        return response(params)
    monkeypatch.setattr(fq,'provider_search',search)
    result=TestClient(app).post('/api/flights/search',json=body())
    assert result.status_code==404 and '귀국편' in result.json()['detail']
    assert not fq.CACHE


@pytest.mark.parametrize('status',[401,403,429,500])
def test_provider_failures_are_safe_and_never_retried(provider,monkeypatch,status):
    calls=[];real=REAL_HTTP_CLIENT
    def handler(request):calls.append(request);return httpx.Response(status,json={'error':'private-flight-test-key'})
    monkeypatch.setenv('SERPAPI_API_KEY','private-flight-test-key')
    monkeypatch.setattr(fq.httpx,'AsyncClient',lambda **kwargs:real(transport=httpx.MockTransport(handler),**kwargs))
    result=TestClient(app).post('/api/flights/search',json=body())
    assert result.status_code in (429,502,503)
    assert 'private-flight-test-key' not in result.text and len(calls)==1


def test_same_airport_and_banned_country_are_rejected_before_search(provider):
    domestic={**TARGET,'cityName':'서울 · 대한민국','category':'domestic','countryCode':'kr'}
    EXTERNAL_CITIES[domestic['cityName']]=domestic
    client=TestClient(app)
    response=client.post('/api/flights/search',json=body(cityName=domestic['cityName'],arrivalAirport='ICN'))
    assert response.status_code==422 and provider==[]
    banned={**TARGET,'cityName':'평양 · 북한','countryCode':'kp'};EXTERNAL_CITIES[banned['cityName']]=banned
    response=client.post('/api/flights/search',json=body(cityName=banned['cityName']))
    assert response.status_code==422 and provider==[]


def test_provider_query_url_is_redacted_from_logs():
    record=logging.LogRecord('httpx',logging.INFO,'',1,'HTTP GET https://serpapi.com/search.json?api_key=private-key&currency=KRW',(),None)
    fq.SecretFilter().filter(record)
    assert 'private-key' not in record.getMessage() and '[redacted]' in record.getMessage()


def test_provider_empty_search_is_404_and_repeated_search_does_not_spend_again(provider,monkeypatch):
    calls=[]
    def handler(request):
        calls.append(request)
        return httpx.Response(200,json={'search_metadata':{'status':'Success'},
             'error':"Google Flights hasn't returned any results for this query."})
    monkeypatch.setattr(fq.httpx,'AsyncClient',lambda **kwargs:REAL_HTTP_CLIENT(transport=httpx.MockTransport(handler),**kwargs))
    client=TestClient(app)
    for _ in range(2):
        reply=client.post('/api/flights/search',json=body())
        assert reply.status_code==404
        assert '검색 결과가 없어요' in reply.json()['detail']
        assert '실제 항공편이 없다는 뜻은 아닙니다' in reply.json()['detail']
        assert body()['departureDate'] in reply.json()['detail']
        assert 'ICN ↔ NRT' in reply.json()['detail']
    assert len(calls)==1
    assert not fq.CACHE
    for cache_key,(_,detail) in list(fq.NO_RESULTS.items()):fq.NO_RESULTS[cache_key]=(0,detail)
    assert client.post('/api/flights/search',json=body()).status_code==404
    assert len(calls)==2


def test_unknown_provider_errors_are_not_cached_as_no_flights(provider,monkeypatch):
    calls=[]
    def handler(request):
        calls.append(request)
        return httpx.Response(200,json={'search_metadata':{'status':'Error','id':'safe-search-id'},
            'error':'temporary provider outage private-flight-test-key'})
    monkeypatch.setattr(fq.httpx,'AsyncClient',lambda **kwargs:REAL_HTTP_CLIENT(transport=httpx.MockTransport(handler),**kwargs))
    client=TestClient(app)
    for _ in range(2):
        reply=client.post('/api/flights/search',json=body())
        assert reply.status_code==502
        assert 'private-flight-test-key' not in reply.text
        assert '검색 결과가 없어요' not in reply.text
    assert len(calls)==2 and not fq.NO_RESULTS


def test_empty_return_search_explains_leg_without_applying_price(provider,monkeypatch):
    calls=[]
    def handler(request):
        params=dict(request.url.params);params.pop('api_key');calls.append(params)
        if 'departure_token' in params:
            return httpx.Response(200,json={'search_metadata':{'status':'Success'},
                'error':"Google Flights hasn't returned any results for this query."})
        return httpx.Response(200,json=response(params))
    monkeypatch.setattr(fq.httpx,'AsyncClient',lambda **kwargs:REAL_HTTP_CLIENT(transport=httpx.MockTransport(handler),**kwargs))
    reply=TestClient(app).post('/api/flights/search',json=body())
    assert reply.status_code==404 and '귀국편 검색 결과가 없어요' in reply.json()['detail']
    assert len(calls)==2 and not fq.CACHE


def test_international_seoul_departure_defaults_to_incheon_without_changing_domestic():
    assert fq.airport_options(TARGET,'seoul')['departureDefault']=='ICN'
    assert fq.airport_options(TARGET,'incheon')['departureDefault']=='ICN'
    domestic={**TARGET,'category':'domestic','countryCode':'kr'}
    assert fq.airport_options(domestic,'seoul')['departureDefault']=='GMP'
