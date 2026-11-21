"""Transparent planning estimates in KRW, not live airline/hotel quotes."""
from datetime import date, timedelta
from math import asin, cos, sin, sqrt, radians, ceil
from typing import Literal
from pydantic import BaseModel, Field, field_validator
from .travel_themes import TravelTheme, THEMES
from .airfare_estimates import planning_airfare

ORIGINS = {
    "seoul": ("서울",37.5665,126.9780), "incheon":("인천",37.4563,126.7052),
    "gyeonggi":("경기",37.2636,127.0286), "gangwon":("강원",37.8813,127.7300),
    "busan":("부산",35.1796,129.0756), "daegu":("대구",35.8714,128.6014),
    "daejeon":("대전",36.3504,127.3845), "gwangju":("광주",35.1595,126.8526),
    "ulsan":("울산",35.5384,129.3114), "sejong":("세종",36.4800,127.2890),
    "chungbuk":("충북",36.6424,127.4890), "chungnam":("충남",36.6588,126.6728),
    "jeonbuk":("전북",35.8242,127.1480), "jeonnam":("전남",34.8161,126.4629),
    "gyeongbuk":("경북",36.5684,128.7294), "gyeongnam":("경남",35.2280,128.6811),
    "jeju":("제주",33.4996,126.5312),
}
Origin = Literal['seoul','incheon','gyeonggi','gangwon','busan','daegu','daejeon','gwangju','ulsan','sejong','chungbuk','chungnam','jeonbuk','jeonnam','gyeongbuk','gyeongnam','jeju']

class TripOptions(BaseModel):
    days: int = Field(default=3, ge=1, le=14, strict=True)
    origin: Origin = "seoul"
    people: int = Field(default=1, ge=1, le=10, strict=True)
    style: Literal['budget','standard','comfort'] = 'standard'
    theme: TravelTheme = 'sightseeing'
    themes: list[TravelTheme] | None = Field(default=None, max_length=7)
    departureDate: date | None = Field(default=None, le=date(2100, 12, 31))
    transportPerPerson: int | None = Field(default=None, ge=0, le=20_000_000, strict=True)
    hotelPerRoomNight: int | None = Field(default=None, ge=0, le=5_000_000, strict=True)

    @field_validator('themes')
    @classmethod
    def unique_themes(cls,values):
        return None if values is None else [key for key in THEMES if key in values]

    @property
    def selected_themes(self):
        return self.themes if self.themes is not None else [self.theme]


# App-maintained planning assumptions: room/night, food/day/person,
# local transit/day/person, sights/day/person. No claim of measured market averages.
PROFILES = {
    'kr':('한국',85000,33000,10000,12000), 'jp':('일본',115000,42000,14000,20000),
    'vn':('베트남',55000,22000,10000,12000), 'th':('태국',65000,26000,12000,18000),
    'tw':('대만',95000,32000,11000,15000), 'sg':('싱가포르',180000,48000,16000,30000),
    'my':('말레이시아',70000,25000,12000,18000), 'id':('인도네시아',65000,25000,15000,18000),
    'ph':('필리핀',65000,25000,14000,18000), 'cn':('중국',85000,30000,12000,18000),
    'us':('미국',230000,70000,25000,35000), 'ca':('캐나다',190000,60000,20000,30000),
    'au':('호주',180000,60000,20000,30000), 'nz':('뉴질랜드',170000,55000,22000,25000),
    'fr':('프랑스',190000,60000,20000,30000), 'it':('이탈리아',160000,52000,18000,25000),
    'gb':('영국',210000,65000,24000,30000), 'de':('독일',160000,50000,20000,23000),
    'es':('스페인',140000,45000,16000,23000), 'ch':('스위스',240000,80000,30000,35000),
    'za':('남아프리카공화국',110000,38000,25000,25000), 'br':('브라질',105000,38000,20000,22000),
    'in':('인도',50000,20000,10000,12000), 'tr':('튀르키예',95000,35000,13000,22000),
}
ALIASES = {'대한민국':'kr','일본':'jp','베트남':'vn','태국':'th','대만':'tw','싱가포르':'sg',
           '미국':'us','캐나다':'ca','호주':'au','뉴질랜드':'nz','프랑스':'fr','이탈리아':'it',
           '영국':'gb','독일':'de','스페인':'es','스위스':'ch','남아프리카공화국':'za','브라질':'br'}

def distance(lat1,lon1,lat2,lon2):
    a = sin(radians(lat2-lat1)/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(radians(lon2-lon1)/2)**2
    return 6371*2*asin(sqrt(min(1,max(0,a))))

def estimate(city, options):
    domestic = city['category'] == 'domestic'
    code = city.get('countryCode','').lower()
    if domestic: code='kr'
    if not code:
        code=next((v for k,v in ALIASES.items() if k in city['cityName']), '')
    profile = PROFILES.get(code,('국가 정보 부족: 해외 공통 가정',130000,45000,20000,25000))
    profile_name, room, food, local, sights = profile
    origin_label, lat, lon = ORIGINS[options.origin]
    km=distance(lat,lon,city['lat'],city['lng'])
    nights=options.days-1
    rooms=ceil(options.people/2)
    lodging_factor,spend_factor = {'budget':(.65,.75),'standard':(1,1),'comfort':(1.65,1.4)}[options.style]
    start=options.departureDate
    weekend_nights=sum((start+timedelta(days=i)).weekday() in (4,5) for i in range(nights)) if start else 0
    # Explicit heuristic uplift, not a holiday calendar or live demand signal.
    peak=bool(start and start.month in (7,8,12))
    seasonal=1.15 if peak else 1
    airfare=None
    if domestic:
        jeju_destination=32.8 <= city['lat'] <= 33.8 and 126 <= city['lng'] <= 127.1
        island_flight=(options.origin=='jeju') != jeju_destination
        transport=190000 if island_flight else min(150000,max(12000,km*320))
        transport_label='국내 왕복 항공 이동' if island_flight else '왕복 철도·버스 이동'
        if km<25 and not island_flight: transport=0
        access=0
    else:
        if options.transportPerPerson is None:
            airfare=planning_airfare(city,code,start,options.days)
        transport=airfare['pricePerPerson'] if airfare else 0
        # Regional departure may require an airport connection; assumption, not route availability.
        access=0 if options.origin in ('seoul','incheon','gyeonggi','busan') else 70000
        transport_label='왕복 이코노미 항공 이동'
    if domestic:transport = round(transport*seasonal)
    if options.transportPerPerson is not None: transport=options.transportPerPerson
    room_rate = round(room*lodging_factor)
    lodging = round(room_rate*rooms*(nights+weekend_nights*.2)*seasonal)
    if options.hotelPerRoomNight is not None:
        room_rate=options.hotelPerRoomNight
        lodging=room_rate*rooms*nights
    themes=set(options.selected_themes)
    theme_extra=0
    items=[]
    def item(key,label,amount,formula,spread=.25,provided=False):
        amount=round(amount)
        items.append({'key':key,'label':label,'amount':amount,'low':round(amount*(1-spread)),
                      'high':round(amount*(1+spread)), 'basis':formula,'source':'사용자 입력' if provided else '계산 추정'})
    item('transport',transport_label,transport*options.people,f'{transport:,}원 × {options.people}명',
         0 if options.transportPerPerson is not None else (.3 if domestic else .45),options.transportPerPerson is not None)
    if airfare:
        items[-1].update(low=airfare['lowPerPerson']*options.people,high=airfare['highPerPerson']*options.people,
            source=airfare['source'],basis=f"{airfare['region']} 기본 {airfare['basePerPerson']:,}원 · "+' · '.join(airfare['adjustments'] or ['날짜 가산 없음'])+f" → 1인 {transport:,}원 × {options.people}명")
    item('access','출발지 공항 연결 교통',access*options.people,f'{access:,}원 × {options.people}명',.3)
    item('lodging','숙박',lodging,f'객실당 1박 기본 {room_rate:,}원 × {rooms}실 × {nights}박'+
         (f' · 금·토 {weekend_nights}박 20% 가산'+(' · 성수기 가정 15% 가산' if peak else '') if options.hotelPerRoomNight is None else ' · 입력 가격 적용'),
         0 if options.hotelPerRoomNight is not None else .35,options.hotelPerRoomNight is not None)
    for key,label,rate in [('food','식비 (하루 3식)',food),('local','현지 교통',local),('sights','관광·입장료',sights)]:
        unit=round(rate*spend_factor)
        formula=f'{unit:,}원 × {options.days}일 × {options.people}명'
        if key=='food' and 'food' in themes:
            adjusted=round(unit*1.3)
            theme_extra+=(adjusted-unit)*options.days*options.people
            formula=f'기본 식비 {unit:,}원 × 맛집 가정 1.3 × {options.days}일 × {options.people}명'
            unit=adjusted
            label='식비 (맛집 테마 포함)'
        item(key,label,unit*options.days*options.people,formula)
    # Explicit planning allowances, not provider prices or spending obligations.
    # Shopping and activities are additional to the base sightseeing allowance.
    for theme,key,label,rate,per_day in [
        ('shopping','shopping','쇼핑 예산',30000 if domestic else 50000,True),
        ('activity','activities','체험·액티비티 예산',25000 if domestic else 40000,True),
        ('nature','trekking','자연·트레킹 준비비',15000 if domestic else 25000,False),
    ]:
        if theme not in themes:
            continue
        amount=rate*options.people*(options.days if per_day else 1)
        formula=f'테마 계획용 {rate:,}원 × '+(f'{options.days}일 × ' if per_day else '여행당 1회 × ')+f'{options.people}명'
        item(key,label,amount,formula,.5)
        theme_extra+=amount
    leisure=[]
    if 'relaxation' in themes:
        leisure.append((10000 if domestic else 15000,'휴양'))
    if 'photography' in themes:
        leisure.append((15000 if domestic else 20000,'감성사진'))
    if leisure:
        rate=max(amount for amount,_ in leisure)
        amount=rate*options.days*options.people
        label='·'.join(label for _,label in leisure)+' 여유 예산'
        formula=f'카페·휴식 등 계획용 {rate:,}원 × {options.days}일 × {options.people}명'
        if len(leisure)>1:
            formula+=' · 겹치는 지출은 큰 배정액으로 1회 반영'
        item('leisure',label,amount,formula,.5)
        theme_extra+=amount
    if not domestic:
        item('insurance','여행자보험', (12000+options.days*1000)*options.people,f'(12,000원 + {options.days}일 × 1,000원) × {options.people}명',.3)
        item('data','통신·eSIM',max(5000,options.days*2000)*options.people,f'1인 {max(5000,options.days*2000):,}원 × {options.people}명',.3)
    subtotal=sum(i['amount'] for i in items)
    item('buffer','예비비 (소계의 10%)',round(subtotal*.1),'교통·숙박·식비 등 소계 × 10%',0)
    low_base=sum(i['low'] for i in items if i['key']!='buffer')
    high_base=sum(i['high'] for i in items if i['key']!='buffer')
    warnings=['실시간 판매가가 아닌 계획용 추정입니다. 항공편·숙소 예약 가능 여부를 확인하지 않았습니다.',
              '성인 기준, 2인 1실(홀수 인원은 객실 추가), 쇼핑은 테마 선택 시 배정액만 포함하며 비자·렌터카·장거리 현지 이동은 별도입니다.',
              '국내 섬·산간 및 해외 소도시는 추가 이동비가 발생할 수 있습니다.']
    if airfare:warnings.append(airfare['notice'])
    if themes-{'sightseeing'}: warnings.append('테마별 가산은 계획용 배정액이며 실제 요금이나 의무 지출이 아닙니다. 휴양·감성사진의 카페·휴식비는 중복 계산하지 않습니다.')
    if not start: warnings.append('출발일 미선택: 주말·성수기 가산을 반영하지 않았습니다.')
    if code not in PROFILES: warnings.append('해당 국가 단가가 없어 해외 공통 단가를 사용했습니다. 예상 범위 밖의 비용도 발생할 수 있습니다.')
    if not domestic and km>6000 and options.days<4: warnings.append('장거리 이동에 비해 여행 기간이 짧습니다. 실제 체류 가능 시간과 항공 일정을 확인하세요.')
    if not domestic and options.days==1: warnings.append('해외 당일치기는 항공편 시간에 따라 불가능할 수 있습니다.')
    return {'total':sum(i['amount'] for i in items),'low':round(low_base*1.1),'high':round(high_base*1.1),
            'perPerson':round(sum(i['amount'] for i in items)/options.people),'items':items,
            'days':options.days,'nights':nights,'people':options.people,'rooms':rooms,'origin':origin_label,
            'profile':profile_name,'distanceKm':round(km),'departureDate':str(start) if start else None,
            'priceType':'estimate','warnings':warnings,'modelVersion':'planning-v3-airfare','airfareEstimate':airfare,
            'themeBudget':{'themes':[THEMES[key][0] for key in options.selected_themes],
                           'additional':theme_extra,'excludesBuffer':True},
            'basis':'앱 관리 국가·지역별 항공 예산, 날짜·인원·기간과 카테고리별 계획용 배정액에 따른 계산. 운임 통계·실시간 환율 자료가 아닙니다.'}

def priced_city(city, options):
    breakdown=estimate(city,options)
    return {**city,'estimatedCost':breakdown['total'],'costIsEstimate':True,'costBreakdown':breakdown}
