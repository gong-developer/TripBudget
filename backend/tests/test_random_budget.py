from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient
from app.main import app, CITIES, EXTERNAL_CITIES
from app.costs import TripOptions, priced_city

client=TestClient(app)

@pytest.fixture(autouse=True)
def clear_registry():
    EXTERNAL_CITIES.clear()
    yield
    EXTERNAL_CITIES.clear()

def test_rejects_expensive_destination_then_returns_affordable():
    expensive=next(c for c in CITIES if '뉴욕' in c['cityName'])
    cheap=CITIES[0]
    budget=priced_city(cheap,TripOptions())['costBreakdown']['high']
    with patch('app.main.budget_candidates',new=AsyncMock(return_value=[expensive,cheap])) as draw:
        response=client.get('/api/destinations/random',params={'category':'all','budget':budget})
    assert response.status_code==200
    data=response.json()
    assert data['city']['cityName']==cheap['cityName']
    assert data['city']['costBreakdown']['high']<=budget
    assert data['budget']==budget
    assert data['budgetBasis']=='upperEstimate'
    draw.assert_awaited_once_with('all')

def test_exhausted_budget_search_never_returns_over_budget():
    with patch('app.main.budget_candidates',new=AsyncMock(return_value=[CITIES[0]])) as draw:
        response=client.get('/api/destinations/random?category=domestic&budget=1')
    assert response.status_code==404
    draw.assert_awaited_once_with('domestic')
    assert 'city' not in response.json()

def test_expected_total_below_budget_but_upper_above_is_rejected():
    city=CITIES[0]
    budget=priced_city(city,TripOptions())['estimatedCost']
    with patch('app.main.budget_candidates',new=AsyncMock(return_value=[city])):
        assert client.get('/api/destinations/random',params={'budget':budget}).status_code==404

def test_budget_filter_includes_duration_group_and_overrides():
    options=TripOptions(days=7,people=3,origin='busan',transportPerPerson=200000,hotelPerRoomNight=120000)
    city=CITIES[1]
    expected=priced_city(city,options)
    budget=expected['costBreakdown']['high']
    params={key:value for key,value in options.model_dump().items() if value is not None}
    with patch('app.main.budget_candidates',new=AsyncMock(return_value=[city])):
        response=client.get('/api/destinations/random',params={**params,'category':'domestic','budget':budget})
    assert response.status_code==200
    assert response.json()['city']['costBreakdown']==expected['costBreakdown']

def test_invalid_budget_never_calls_provider():
    with patch('app.main.budget_candidates',new=AsyncMock()) as draw:
        for params in ({'budget':0},{'budget':-1},{'budget':100000001},{'budget':'text'},{'budget':1.5}):
            assert client.get('/api/destinations/random',params=params).status_code==422
    draw.assert_not_awaited()

def test_unrestricted_dart_returns_first_destination_without_cost_filter():
    expensive=next(c for c in CITIES if '뉴욕' in c['cityName'])
    with patch('app.main.random_destination',new=AsyncMock(return_value=expensive)) as draw:
        response=client.get('/api/destinations/random?category=international&days=14&people=10')
    assert response.status_code==200
    assert response.json()['city']['cityName']==expensive['cityName']
    assert response.json()['budget'] is None
    assert response.json()['budgetBasis']=='unrestricted'
    draw.assert_awaited_once_with('international')
