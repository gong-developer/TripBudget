import json
from unittest.mock import AsyncMock, patch
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.main import app, CITIES, EXTERNAL_CITIES
from app.costs import TripOptions, priced_city

client = TestClient(app)


@pytest.fixture(autouse=True)
def registry():
    EXTERNAL_CITIES.clear()
    yield
    EXTERNAL_CITIES.clear()


def events(response):
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


def test_comparison_streams_real_steps_and_distinct_affordable_candidates():
    candidates=CITIES[:6]
    budget=max(priced_city(city,TripOptions())['costBreakdown']['high'] for city in candidates)
    with patch('app.travel_features.budget_candidates',new=AsyncMock(return_value=candidates)):
        response=client.post('/api/destinations/compare',json={'budget':budget,'category':'all'})
    data=events(response)
    assert response.headers['content-type'].startswith('application/x-ndjson')
    assert [event.get('phase') for event in data[:4]]==['fetch','compare','sights','names']
    result=data[-1]
    assert result['type']=='result' and len(result['cities'])==len(candidates)
    assert len({city['cityName'] for city in result['cities']})==len(candidates)
    assert all(city['costBreakdown']['high']<=budget for city in result['cities'])
    upper_costs=[city['costBreakdown']['high'] for city in result['cities']]
    assert upper_costs==sorted(upper_costs)
    assert all(city['cityName'] in EXTERNAL_CITIES for city in result['cities'])


def test_comparison_returns_available_candidate_count_without_duplicates():
    with patch('app.travel_features.budget_candidates',new=AsyncMock(return_value=[CITIES[0],CITIES[0]])):
        data=events(client.post('/api/destinations/compare',json={'budget':10000000}))
    assert len(data[-1]['cities'])==1


def test_comparison_stream_errors_are_explicit_and_do_not_return_over_budget():
    with patch('app.travel_features.budget_candidates',new=AsyncMock(return_value=[CITIES[0]])):
        data=events(client.post('/api/destinations/compare',json={'budget':1}))
    assert data[-1]['type']=='error' and data[-1]['status']==404
    assert not any(event['type']=='result' for event in data)


def test_provider_failure_stream_has_safe_message():
    with patch('app.travel_features.budget_candidates',new=AsyncMock(side_effect=HTTPException(429,'사용 한도 초과'))):
        data=events(client.post('/api/destinations/compare',json={'budget':1000000}))
    assert data[-1]=={'type':'error','status':429,'message':'사용 한도 초과'}


def test_restore_recalculates_cost_and_survives_registry_loss():
    city={**CITIES[0],'estimatedCost':1,'costBreakdown':{'total':1},'regionName':'서울특별시 · 종로구'}
    response=client.post('/api/destinations/restore',json={'cities':[city],'people':3,'days':5})
    assert response.status_code==200
    restored=response.json()['cities'][0]
    assert restored['estimatedCost']==priced_city(CITIES[0],TripOptions(people=3,days=5))['estimatedCost']
    assert restored['estimatedCost']!=1
    assert restored['cityName'] in EXTERNAL_CITIES
    assert restored['regionName'] == city['regionName']
    with patch('app.travel_features.nearby_places',new=AsyncMock(return_value={'places':[]})):
        assert client.post('/api/nearby-places',json={'cityName':restored['cityName']}).status_code==200


def test_invalid_restore_and_missing_destination_rejected():
    assert client.post('/api/destinations/restore',json={'cities':[]}).status_code==422
    assert client.post('/api/destinations/restore',json={'cities':[{**CITIES[0],'lat':999}]}).status_code==422
    assert client.post('/api/day-route',json={'cityName':'unknown','placeNames':['명소 하나','명소 둘']}).status_code==404
    assert client.post('/api/day-route',json={'cityName':CITIES[0]['cityName'],'placeNames':['하나']}).status_code==422
