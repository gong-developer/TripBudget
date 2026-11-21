import json
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient
from app.main import app, CITIES
from app.costs import TripOptions, estimate, priced_city
from plan_fixtures import quality_response

client=TestClient(app)
busan=CITIES[0]
tokyo=next(c for c in CITIES if '도쿄' in c['cityName'])

def amounts(result):
    return {item['key']:item['amount'] for item in result['items']}

@pytest.mark.parametrize('days',[1,3,14])
@pytest.mark.parametrize('people',[1,2,3,10])
def test_totals_nights_and_bounds(days,people):
    result=estimate(tokyo,TripOptions(days=days,people=people))
    assert result['total']==sum(i['amount'] for i in result['items'])
    assert result['low']<=result['total']<=result['high']
    assert result['nights']==days-1
    assert result['rooms']==(people+1)//2
    if days==1: assert amounts(result)['lodging']==0

def test_real_quotes_override_only_matching_items():
    options=TripOptions(days=5,people=3,departureDate=date(2027,8,6),transportPerPerson=320000,hotelPerRoomNight=90000)
    result=estimate(tokyo,options)
    costs=amounts(result)
    assert costs['transport']==960000
    assert costs['lodging']==90000*2*4
    for item in result['items']:
        if item['key'] in ('transport','lodging'):
            assert item['source']=='사용자 입력'
            assert item['low']==item['amount']==item['high']
    free=amounts(estimate(tokyo,TripOptions(transportPerPerson=0,hotelPerRoomNight=0)))
    assert free['transport']==free['lodging']==0

def test_origin_and_destination_affect_transport():
    seoul=amounts(estimate(busan,TripOptions(origin='seoul')))
    local=amounts(estimate(busan,TripOptions(origin='busan')))
    assert local['transport']==0
    assert seoul['transport']>local['transport']
    jeju=estimate(busan,TripOptions(origin='jeju'))
    assert '항공' in jeju['items'][0]['label']

def test_style_days_country_and_calendar_change_costs():
    budget=estimate(tokyo,TripOptions(style='budget'))['total']
    standard=estimate(tokyo,TripOptions())['total']
    comfort=estimate(tokyo,TripOptions(style='comfort'))['total']
    assert budget<standard<comfort
    assert estimate(tokyo,TripOptions(days=14))['total']>standard
    weekday=estimate(tokyo,TripOptions(departureDate=date(2027,5,10)))
    weekend=estimate(tokyo,TripOptions(departureDate=date(2027,5,7)))
    assert amounts(weekend)['lodging']>amounts(weekday)['lodging']
    thailand={**tokyo,'countryCode':'th'}
    # Country living-cost profiles are independent from the new country airfare budget.
    assert amounts(estimate(thailand,TripOptions()))['food']<amounts(estimate(tokyo,TripOptions()))['food']
    assert amounts(estimate(thailand,TripOptions()))['lodging']<amounts(estimate(tokyo,TripOptions()))['lodging']

def test_unknown_country_has_explicit_fallback():
    result=estimate({**tokyo,'cityName':'Unknown','countryCode':'zz'},TripOptions())
    assert any('공통 단가' in text for text in result['warnings'])
    assert result['priceType']=='estimate'

@pytest.mark.parametrize('options',[{'origin':'bad'},{'people':0},{'people':True},{'style':'bad'},
                                    {'days':15},{'departureDate':'not-a-date'}, {'transportPerPerson':-1},
                                    {'hotelPerRoomNight':1.5}])
def test_invalid_cost_inputs(options):
    response=client.post('/api/estimate',json={'cityName':busan['cityName'],**options})
    assert response.status_code==422

def test_recommendation_uses_same_cost_engine():
    options={'days':7,'people':3,'origin':'busan','style':'budget'}
    response=client.post('/api/recommend',json={'budget':10000000,'category':'domestic',**options})
    assert response.status_code==200
    for city in response.json()['cities']:
        cost=client.post('/api/estimate',json={'cityName':city['cityName'],**options}).json()
        assert cost==city['costBreakdown']
        assert city['estimatedCost']==cost['total']

def test_ai_uses_identical_group_estimate(monkeypatch):
    monkeypatch.delenv('GEMINI_ITINERARY_MODEL',raising=False)
    monkeypatch.setenv('GEMINI_MODEL','gemini-1.5-flash-latest')
    monkeypatch.setenv('DEMO_MODE','false')
    monkeypatch.setenv('GEMINI_API_KEY','test-placeholder')
    options={'days':4,'people':2,'origin':'jeju','style':'comfort','hotelPerRoomNight':170000}
    with patch('app.compact_itinerary._generate_fast',new=AsyncMock(return_value=quality_response(4))) as generate:
        response=client.post('/api/generate-itinerary',json={'cityName':tokyo['cityName'],'budget':5000000,**options})
    assert response.status_code==200
    payload=json.loads(generate.call_args.args[0])
    assert 'people' not in payload and 'costEstimate' not in payload
    assert f"{estimate(tokyo,TripOptions(**options))['total']:,}원" in response.json()['text']
    assert '2명 전체' in response.json()['text']

def test_random_request_options_and_validation():
    with patch('app.main.budget_candidates',new=AsyncMock(return_value=[tokyo])):
        response=client.get('/api/destinations/random?budget=100000000&category=international&days=7&people=2&origin=busan')
    assert response.status_code==200
    cost=response.json()['city']['costBreakdown']
    assert cost['days']==7 and cost['people']==2 and cost['origin']=='부산'
    assert response.json()['city']['estimatedCost']==cost['total']
    assert client.get('/api/destinations/random?budget=100000000&origin=invalid').status_code==422
    assert client.get('/api/destinations/random?budget=100000000&departureDate=bad').status_code==422
