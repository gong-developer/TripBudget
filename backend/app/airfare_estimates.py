"""App-chosen airfare budgets, not measured fares or availability predictions."""
from datetime import datetime,timedelta,timezone
from functools import lru_cache
import json
from math import asin,cos,radians,sin,sqrt
from pathlib import Path

# KRW per person, round trip, economy. All three values are planning assumptions.
REGIONS={
 'japan':('일본',400000,220000,750000),
 'china':('중국',450000,250000,850000),
 'taiwan':('대만·홍콩·마카오',400000,220000,750000),
 'southeast':('동남아',550000,300000,1000000),
 'southasia':('남아시아',900000,550000,1600000),
 'centralasia':('중앙아시아·몽골',850000,500000,1500000),
 'middleeast':('중동',1200000,750000,2200000),
 'europe':('유럽',1400000,900000,2400000),
 'northamerica':('북미',1700000,1050000,2900000),
 'latin':('중남미·카리브',2500000,1600000,4300000),
 'africa':('아프리카',2300000,1400000,4000000),
 'oceania':('호주·뉴질랜드',1400000,850000,2400000),
 'pacific':('태평양 도서',1300000,750000,2400000),
 'near_pacific':('괌·북마리아나',650000,350000,1200000),
 'other':('기타 해외 공통',1800000,1000000,3300000),
}
COUNTRIES={
 'japan':'jp','china':'cn','taiwan':'tw hk mo',
 'southeast':'vn th my sg id ph kh la mm bn tl',
 'southasia':'in np bt bd lk mv pk',
 'centralasia':'mn kz uz kg tj tm',
 'middleeast':'ae qa om sa bh kw jo lb il ps tr ge am az',
 'europe':'al ad at be ba bg by ch cy cz de dk ee es fi fo fr gb gi gr hr hu ie is it li lt lu lv mc md me mk mt nl no pl pt ro rs se si sk sm va xk',
 'northamerica':'us ca',
 'latin':'mx bz cr sv gt hn ni pa ar bo br cl co ec fk gf gy pe py sr uy ve ag ai aw bb bl bm bq bs cu cw dm do gd gp ht jm kn ky lc mf mq ms pr sx tc tt vc vg vi',
 'africa':'dz ao bj bf bi bw cd cf cg ci cm cv dj eg eh er et ga gh gm gn gq gw ke km lr ls ly ma mg ml mr mu mw mz na ne ng re rw sc sd sh sl sn so ss st sz td tg tn tz ug yt za zm zw',
 'oceania':'au nz','pacific':'as ck fj fm ki mh nc nf nr nu pf pg pn pw sb tk to tv vu wf ws',
 'near_pacific':'gu mp',
}
COUNTRY_REGION={code:region for region,codes in COUNTRIES.items() for code in codes.split()}
# Geographic reference airports only; this list makes no claim about direct flights.
GATEWAYS=set('ICN PUS NRT HND KIX NGO FUK CTS OKA PEK PKX PVG SHA CAN SZX CTU TFU XIY TAO DLC TPE KHH HKG MFM HAN SGN DAD BKK DMK HKT CNX SIN KUL PEN BKI CGK DPS MNL CEB PNH VTE RGN BWN DEL BOM BLR MAA CCU KTM CMB DAC MLE KHI ISB UBN ALA TAS DXB AUH DOH MCT RUH JED BAH AMM TLV IST SAW TBS EVN GYD LHR LGW CDG ORY AMS FRA MUC FCO MXP MAD BCN LIS ZRH VIE BRU CPH ARN OSL HEL WAW PRG BUD ATH IST SVO DME LED KEF DUB YYZ YVR YUL YYC LAX SFO SEA JFK EWR IAD BOS ORD DFW ATL IAH DEN LAS SLC PHX SAN MIA MCO HNL ANC GUM SPN MEX CUN SJO PTY BOG LIM SCL EZE GRU GIG UIO GYE MVD ASU LPB VVI KIN MBJ NAS PUJ SDQ SJU HAV POS UVF CAI CMN RAK ALG TUN ADD NBO DAR JNB CPT DUR LOS ACC DSS MRU SEZ SYD MEL BNE PER ADL OOL CNS DRW AKL CHC WLG NAN PPT POM NOU RAR'.split())


def current_date():
 return datetime.now(timezone(timedelta(hours=9))).date()


def distance(lat1,lng1,lat2,lng2):
 a=sin(radians(lat2-lat1)/2)**2+cos(radians(lat1))*cos(radians(lat2))*sin(radians(lng2-lng1)/2)**2
 return 6371*2*asin(sqrt(min(1,max(0,a))))


@lru_cache(maxsize=1)
def gateways():
 rows=json.loads((Path(__file__).resolve().parents[1]/'data/flight-airports.json').read_text())['airports']
 return [row for row in rows if row['code'] in GATEWAYS]


def planning_airfare(city,code,departure,days):
 region=COUNTRY_REGION.get(code,'other')
 if code=='ru':region='centralasia' if city['lng']>=60 else 'europe'
 label,base,low,high=REGIONS[region]
 if code in ('us','ca') and city['lng']<-100:
  label='북미 서부·하와이';base,low,high=1400000,850000,2400000
 # Proximity is a heuristic for a possible additional connection, not flight data.
 local=[row for row in gateways() if row['countryCode']==code]
 nearest=min(local,key=lambda row:distance(city['lat'],city['lng'],row['lat'],row['lng'])) if local else None
 gateway_km=round(distance(city['lat'],city['lng'],nearest['lat'],nearest['lng'])) if nearest else None
 extra=0;adjustments=[]
 if gateway_km is None or gateway_km>120:
  extra=200000 if region in ('japan','china','taiwan','southeast','near_pacific') else 450000
  adjustments.append(f'주요 공항권 밖 연결 예산 가정 +{extra:,}원')
 central=base+extra;lower=low+extra*.5;upper=high+extra*1.5
 multiplier=1
 if departure:
  lead=(departure-current_date()).days
  if 0<=lead<=7:
   multiplier*=1.6;adjustments.append('출발 7일 이내 가정 +60%')
  elif 8<=lead<=14:
   multiplier*=1.35;adjustments.append('출발 8~14일 전 가정 +35%')
  elif 15<=lead<=30:
   multiplier*=1.15;adjustments.append('출발 15~30일 전 가정 +15%')
  peak=(12,1,2,7,8) if region in ('southeast','oceania','pacific','near_pacific') else (7,8,12)
  if region=='japan':peak=(3,4,7,8,12)
  if departure.month in peak:
   multiplier*=1.15;adjustments.append('월별 성수기 가정 +15%')
  end=departure+timedelta(days=days-1)
  if departure.weekday() in (4,5,6) or end.weekday() in (4,5,6):
   multiplier*=1.1;adjustments.append('출국·귀국 주말 포함 가정 +10% (1회)')
 else:adjustments.append('날짜 미정: 예약 시점·성수기·주말 가산 미적용')
 rounded=lambda value:int(round(value*multiplier/10000)*10000)
 return {'method':'planning_rules','region':label,'basePerPerson':base,
         'pricePerPerson':rounded(central),'lowPerPerson':rounded(lower),'highPerPerson':rounded(upper),
         'adjustments':adjustments,'referenceAirport':nearest['code'] if nearest else None,
         'referenceAirportDistanceKm':gateway_km,
         'source':'앱 설정 계획용 가정','basisVersion':'airfare-planning-2026-11',
         'notice':'조사된 평균 운임·예약 가능 가격·통계적 신뢰구간이 아닙니다. 실제 노선·좌석·공휴일·수하물 요금은 조회하지 않았습니다.'}
