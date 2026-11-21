from datetime import date,timedelta
import pytest
from app import airfare_estimates as fares
from app.costs import TripOptions,estimate

TOKYO={'cityName':'도쿄 · 일본','countryCode':'jp','category':'international','lat':35.68,'lng':139.69}


def transport(cost):
 return next(row for row in cost['items'] if row['key']=='transport')


def test_region_budgets_and_remote_connections_are_distinct():
 tokyo=estimate(TOKYO,TripOptions())
 paris=estimate({**TOKYO,'countryCode':'fr','lat':48.85,'lng':2.35},TripOptions())
 natales=estimate({**TOKYO,'countryCode':'cl','lat':-51.73,'lng':-72.5},TripOptions())
 assert transport(tokyo)['amount']==400000
 assert transport(paris)['amount']==1400000
 assert transport(natales)['amount']==2950000
 assert natales['airfareEstimate']['referenceAirportDistanceKm']>120
 assert '연결 예산' in natales['airfareEstimate']['adjustments'][0]
 assert transport(tokyo)['source']=='앱 설정 계획용 가정'
 assert all(transport(cost)['low']<=transport(cost)['amount']<=transport(cost)['high'] for cost in [tokyo,paris,natales])


@pytest.mark.parametrize('lead,expected',[(0,640000),(7,640000),(8,540000),(14,540000),(15,460000),(30,460000),(31,400000)])
def test_booking_window_boundaries_are_applied_once(monkeypatch,lead,expected):
 departure=date(2027,6,7) # Monday, outside assumed Japan peak months; Wednesday return
 monkeypatch.setattr(fares,'current_date',lambda:departure-timedelta(days=lead))
 cost=estimate(TOKYO,TripOptions(departureDate=departure))
 assert transport(cost)['amount']==expected


def test_weekend_and_peak_assumptions_do_not_duplicate_existing_seasonal_uplift(monkeypatch):
 monkeypatch.setattr(fares,'current_date',lambda:date(2026,11,1))
 # Monday departure and Wednesday return: only the airfare's 15% December uplift.
 cost=estimate(TOKYO,TripOptions(departureDate=date(2026,12,7)))
 assert transport(cost)['amount']==460000
 weekend=estimate(TOKYO,TripOptions(departureDate=date(2026,12,4)))
 assert transport(weekend)['amount']==510000 # 400,000 × 1.15 × 1.1, rounded to 10,000
 assert sum('주말' in text for text in weekend['airfareEstimate']['adjustments'])==1


def test_manual_and_live_fare_overrides_bypass_all_planning_uplifts(monkeypatch):
 monkeypatch.setattr(fares,'current_date',lambda:date(2026,12,4))
 for price in (0,389776,500000):
  cost=estimate(TOKYO,TripOptions(people=3,departureDate=date(2026,12,4),transportPerPerson=price))
  assert cost['airfareEstimate'] is None
  assert transport(cost)['amount']==price*3
  assert transport(cost)['low']==transport(cost)['high']==price*3
  assert transport(cost)['source']=='사용자 입력'


def test_ranges_scale_with_people_and_feed_total_bounds():
 single=estimate(TOKYO,TripOptions())
 group=estimate(TOKYO,TripOptions(people=3))
 for field in ('amount','low','high'):assert transport(group)[field]==transport(single)[field]*3
 assert group['total']==sum(item['amount'] for item in group['items'])
 assert group['low']<=group['total']<=group['high']
 assert any('평균 운임' in text for text in group['warnings'])


def test_unknown_country_is_explicit_and_domestic_keeps_previous_logic():
 unknown=estimate({**TOKYO,'countryCode':'zz'},TripOptions())
 assert unknown['airfareEstimate']['region']=='기타 해외 공통'
 domestic=estimate({'cityName':'부산','category':'domestic','countryCode':'kr','lat':35.18,'lng':129.07},TripOptions(origin='jeju'))
 assert domestic['airfareEstimate'] is None
 assert transport(domestic)['amount']==190000
