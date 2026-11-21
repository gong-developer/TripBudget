import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app import destination_sights as sights
from app.sight_errors import NoSights
from app.main import app, CITIES, EXTERNAL_CITIES


def city(index=0):
    return {**CITIES[0],'cityName':f'확인 지역 {index}','estimatedCost':200000+index*10000}


def places(region,days=3):
    return {'places':[{'name':f'실제 관광명소 {i}','lat':region['lat']+i*.001,'lng':region['lng']} for i in range(days*2)],'source':'test'}


def test_only_verified_regions_survive_empty_and_connection_failures(monkeypatch):
    async def fetch(region,days):
        if region['cityName']==city(1)['cityName']:return {'places':[]}
        if region['cityName']==city(2)['cityName']:raise HTTPException(503,'provider unavailable')
        return places(region,days)
    monkeypatch.setattr(sights,'fetch_nearby',fetch)
    result=asyncio.run(sights.confirmed_destinations([city(i) for i in range(3)]))
    assert [row['cityName'] for row in result]==[city(0)['cityName']]
    assert result[0]['sightsVerified'] and result[0]['sightCount']==6


def test_same_region_shares_probe_and_cache(monkeypatch):
    fetch=AsyncMock(side_effect=places)
    monkeypatch.setattr(sights,'fetch_nearby',fetch)
    async def run():
        first,second=await asyncio.gather(sights.confirmed_nearby(city()),sights.confirmed_nearby(city()))
        assert first==second==await sights.confirmed_nearby(city())
    asyncio.run(run())
    fetch.assert_awaited_once()


def test_actual_no_sights_is_briefly_cached_but_outage_is_not(monkeypatch):
    async def run():
        empty=AsyncMock(side_effect=NoSights(503,'no sights'))
        monkeypatch.setattr(sights,'fetch_nearby',empty)
        assert await sights.confirmed_nearby(city())=={'places':[]}
        assert await sights.confirmed_destinations([city()])==[]
        empty.assert_awaited_once()
        assert next(iter(sights.CACHE.values()))[0]<sights.time.monotonic()+181
        failing=AsyncMock(side_effect=HTTPException(503,'missing API key'))
        monkeypatch.setattr(sights,'fetch_nearby',failing)
        for _ in range(2):
            with pytest.raises(HTTPException) as error:
                await sights.confirmed_destinations([city(1)])
            assert error.value.detail=='missing API key'
        assert failing.await_count==2
        assert sights.cached_sights(city(1)) is None
    asyncio.run(run())


def test_probe_and_concurrency_limits_preserve_variety(monkeypatch):
    active=0;maximum=0;calls=[]
    async def fetch(region,days):
        nonlocal active,maximum
        active+=1;maximum=max(maximum,active);calls.append(region['cityName'])
        await asyncio.sleep(.001)
        active-=1
        return places(region,days)
    monkeypatch.setattr(sights,'fetch_nearby',fetch)
    candidates=[{**city(i),'estimatedCost':(i%3+1)*500000} for i in range(18)]
    result=asyncio.run(sights.confirmed_destinations(candidates,limit=6))
    assert len(result)==len(calls)==6
    assert maximum<=4
    assert len({row['estimatedCost'] for row in result})==3


def test_invalid_place_rows_are_not_evidence_of_sights(monkeypatch):
    monkeypatch.setattr(sights,'fetch_nearby',AsyncMock(return_value={'places':[
        {'name':'','lat':35,'lng':129},{'name':'invalid','lat':999,'lng':129},
        {'name':'전체메뉴','lat':35,'lng':129}]}))
    assert asyncio.run(sights.confirmed_destinations([city()]))==[]


def test_slow_unconfirmed_region_is_not_returned_with_verified_regions(monkeypatch):
    async def fetch(region,days):
        if region['cityName']==city(1)['cityName']:await asyncio.sleep(1)
        return places(region,days)
    monkeypatch.setattr(sights,'fetch_nearby',fetch)
    result=asyncio.run(sights.confirmed_destinations([city(),city(1)],timeout=.01))
    assert [row['cityName'] for row in result]==[city()['cityName']]


def test_roulette_retries_when_first_region_has_no_sights(monkeypatch):
    async def fetch(region,days):
        return {'places':[]} if region['cityName']==city()['cityName'] else places(region,days)
    monkeypatch.setattr(sights,'fetch_nearby',fetch)
    with patch('app.main.random_destination',AsyncMock(side_effect=[city(),city(1)])) as provider:
        response=TestClient(app).get('/api/destinations/random')
    assert response.status_code==200
    assert response.json()['city']['cityName']==city(1)['cityName']
    assert response.json()['city']['sightsVerified']
    assert provider.await_count==2


def test_comparison_drops_empty_previous_registry_regions(monkeypatch):
    empty=city(1);EXTERNAL_CITIES[empty['cityName']]=empty
    async def fetch(region,days):
        return {'places':[]} if region['cityName']==empty['cityName'] else places(region,days)
    monkeypatch.setattr(sights,'fetch_nearby',fetch)
    with patch('app.travel_features.budget_candidates',AsyncMock(return_value=[city(),empty])):
        response=TestClient(app).post('/api/destinations/compare',json={'budget':10000000})
    result=json.loads(response.text.splitlines()[-1])
    assert result['type']=='result'
    assert [row['cityName'] for row in result['cities']]==[city()['cityName']]


def test_no_verified_candidates_returns_explanation_without_empty_region_cards(monkeypatch):
    monkeypatch.setattr(sights,'fetch_nearby',AsyncMock(return_value={'places':[]}))
    with patch('app.travel_features.budget_candidates',AsyncMock(return_value=[city()])):
        response=TestClient(app).post('/api/destinations/compare',json={'budget':10000000})
    result=json.loads(response.text.splitlines()[-1])
    assert result['type']=='error' and result['status']==404
    assert '관광명소' in result['message']
    with patch('app.main.random_destination',AsyncMock(return_value=city())) as provider:
        response=TestClient(app).get('/api/destinations/random')
    assert response.status_code==404 and provider.await_count==3


@pytest.mark.parametrize('days',[1,3,7,14])
def test_minimum_sights_matches_selected_trip_length(monkeypatch,days):
    async def fetch(region,requested_days):
        assert requested_days==days
        rows=places(region,days)['places']
        return {'places':rows[:-1] if region['cityName']==city()['cityName'] else rows}
    monkeypatch.setattr(sights,'fetch_nearby',fetch)
    result=asyncio.run(sights.confirmed_destinations([city(),city(1)],days=days))
    assert [row['cityName'] for row in result]==[city(1)['cityName']]
    assert result[0]['sightCount']==days*2


def test_cache_for_short_trips_cannot_admit_long_trips_or_hide_short_trips(monkeypatch):
    fetch=AsyncMock(return_value=places(city(),3))
    monkeypatch.setattr(sights,'fetch_nearby',fetch)
    async def run():
        assert len(await sights.confirmed_destinations([city()],days=3))==1
        assert await sights.confirmed_destinations([city()],days=4)==[]
        assert len(await sights.confirmed_destinations([city()],days=3))==1
        assert await sights.confirmed_destinations([city()],days=4)==[]
    asyncio.run(run())
    assert fetch.await_count==2


def test_duplicate_names_do_not_fill_required_itinerary_slots(monkeypatch):
    rows=places(city(),3)['places']
    for row in rows:row['originalName']='Same sight'
    monkeypatch.setattr(sights,'fetch_nearby',AsyncMock(return_value={'places':rows}))
    assert asyncio.run(sights.confirmed_destinations([city()],days=3))==[]


def test_recommendations_and_roulette_use_requested_days(monkeypatch):
    async def fetch(region,days):
        assert days==7
        return places(region,6 if region['cityName']==city()['cityName'] else 7)
    monkeypatch.setattr(sights,'fetch_nearby',fetch)
    EXTERNAL_CITIES[city()['cityName']]=city()
    EXTERNAL_CITIES[city(1)['cityName']]=city(1)
    client=TestClient(app)
    with patch('app.travel_features.budget_candidates',AsyncMock(return_value=[city(),city(1)])):
        response=client.post('/api/destinations/compare',json={'budget':10000000,'days':7})
    result=json.loads(response.text.splitlines()[-1])
    assert result['type']=='result' and len(result['cities'])==1
    assert result['cities'][0]['cityName']==city(1)['cityName']
    with patch('app.main.random_destination',AsyncMock(side_effect=[city(),city(1)])) as provider:
        response=client.get('/api/destinations/random?days=7')
    assert response.status_code==200 and provider.await_count==2
    assert response.json()['city']['sightCount']==14
    with patch('app.main.budget_candidates',AsyncMock(return_value=[city(),city(1)])):
        response=client.get('/api/destinations/random?days=7&budget=10000000')
    assert response.status_code==200
    assert response.json()['city']['cityName']==city(1)['cityName']
    response=client.post('/api/recommend',json={'budget':10000000,'days':7,
        'destinationNames':[city()['cityName'],city(1)['cityName']]})
    assert response.status_code==200
    assert [row['cityName'] for row in response.json()['cities']]==[city(1)['cityName']]
    with patch('app.main.search_destinations',AsyncMock(return_value=[city(),city(1)])):
        response=client.get('/api/destinations/search?q=테스트&days=7')
    assert response.status_code==200
    assert [row['cityName'] for row in response.json()['cities']]==[city(1)['cityName']]


def test_insufficient_sights_explain_shortening_trip(monkeypatch):
    monkeypatch.setattr(sights,'fetch_nearby',AsyncMock(return_value=places(city(),2)))
    with patch('app.travel_features.budget_candidates',AsyncMock(return_value=[city()])):
        response=TestClient(app).post('/api/destinations/compare',json={'budget':10000000,'days':3})
    event=json.loads(response.text.splitlines()[-1])
    assert event['type']=='error' and event['status']==404
    assert '여행 기간을 줄이거나' in event['message']


def test_probe_uses_full_itinerary_lookup_distance_and_deduplication(monkeypatch):
    from app.itinerary_context import prepare_itinerary
    from app.costs import TripOptions
    from app.compact_itinerary import plan_input
    async def actual_probe(region,days):
        return await prepare_itinerary(plan_input(region,TripOptions(days=days)),require_sufficient=False)
    monkeypatch.setattr(sights,'fetch_nearby',actual_probe)
    region={**city(),'countryCode':'kr','destinationType':'region','regionId':'test-region'}
    rows=places(region,14)['places']
    rows=[{**row,'originalName':row['name']} for row in rows]
    rows.extend([{**rows[0]},{**rows[0],'name':'멀리 있는 명소','originalName':'멀리 있는 명소','lat':region['lat']+1}])
    provider=AsyncMock(return_value={'places':rows})
    monkeypatch.setattr('app.domestic_sights.domestic_sights',provider)
    result=asyncio.run(sights.confirmed_destinations([region],days=14))
    assert len(result)==1 and result[0]['sightCount']==28
    provider.assert_awaited_once()
    assert provider.await_args.kwargs['limit']==48
