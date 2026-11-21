import asyncio
import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.main import app, CITIES, EXTERNAL_CITIES
from app.countries import country_boundaries, country_info, filter_country
from app.geoapify_destinations import overseas_candidates
from app.destinations import budget_candidates, random_destination

client=TestClient(app)


def test_country_boundaries_include_small_countries_and_valid_search_metadata():
    response=client.get('/api/countries')
    assert response.status_code==200
    data=response.json()
    assert len(data['features'])>=190
    assert country_info('jp')['name']=='일본'
    assert country_info('sg')['name']=='싱가포르'
    for feature in data['features']:
        country=feature['properties']
        assert len(country['code'])==2
        assert len(country['bounds'])==2
        assert country['bounds'][0][0]<=country['bounds'][1][0]
        assert country['bounds'][0][1]<=country['bounds'][1][1]
        assert feature['geometry']['type'] in ('Polygon','MultiPolygon')


def test_overseas_provider_uses_country_boundary_and_rejects_foreign_country_rows(monkeypatch):
    monkeypatch.setenv('GEOAPIFY_API_KEY','secret-test')
    calls=[]
    def handler(request):
        calls.append(request)
        if request.url.path.endswith('/search'):
            assert request.url.params['type']=='country'
            assert request.url.params['filter']=='countrycode:jp'
            return httpx.Response(200,json={'results':[{'country_code':'jp','place_id':'jp-boundary'}]})
        assert request.url.params['filter']=='place:jp-boundary'
        assert request.url.params['limit']=='120'
        return httpx.Response(200,json={'features':[
            {'properties':{'name':'Tokyo','country':'Japan','country_code':'jp','lat':35.6,'lon':139.7}},
            {'properties':{'name':'Paris','country':'France','country_code':'fr','lat':48.8,'lon':2.3}}]})
    real_client=httpx.AsyncClient
    with patch('app.geoapify_destinations.httpx.AsyncClient',side_effect=lambda **kw:real_client(transport=httpx.MockTransport(handler))):
        cities=asyncio.run(overseas_candidates(country_code='jp'))
    assert len(cities)==1 and cities[0]['countryCode']=='jp'
    assert len(calls)==2


def test_country_routing_does_not_call_the_other_provider():
    async def run():
        with patch('app.destinations.overseas_candidates',new=AsyncMock(return_value=[{'countryCode':'jp'}])) as overseas, \
             patch('app.destinations.domestic_budget_candidates',new=AsyncMock(return_value=[{'category':'domestic'}])) as domestic:
            await budget_candidates('all','jp')
            overseas.assert_awaited_once_with(country_code='jp')
            domestic.assert_not_awaited()
            await budget_candidates('all','kr')
            domestic.assert_awaited_once_with()
            assert overseas.await_count==1
    asyncio.run(run())


def test_country_mismatch_or_unknown_code_never_calls_provider():
    with patch('app.main.random_destination',new=AsyncMock()) as provider:
        for params in ({'category':'domestic','countryCode':'jp'},
                       {'category':'international','countryCode':'kr'},
                       {'countryCode':'zz'},{'countryCode':'JAPAN'}):
            assert client.get('/api/destinations/random',params=params).status_code==422
    provider.assert_not_awaited()


def test_comparison_filters_previous_registry_candidates_by_country():
    tokyo=next(city for city in CITIES if '도쿄' in city['cityName'])
    EXTERNAL_CITIES.clear()
    foreign={**CITIES[0],'countryCode':'kr'}
    EXTERNAL_CITIES[foreign['cityName']]=foreign
    try:
        with patch('app.travel_features.budget_candidates',new=AsyncMock(return_value=[{**tokyo,'countryCode':'jp'}])) as provider:
            response=client.post('/api/destinations/compare',json={'budget':10000000,'category':'international','countryCode':'jp'})
        result=json.loads(response.text.splitlines()[-1])
        assert result['type']=='result'
        assert all(city['countryCode']=='jp' for city in result['cities'])
        provider.assert_awaited_once_with('international','jp')
    finally:
        EXTERNAL_CITIES.clear()


def test_missing_country_boundary_never_queries_an_unrestricted_region(monkeypatch):
    monkeypatch.setenv('GEOAPIFY_API_KEY','secret-test')
    with patch('app.geoapify_destinations.geo_request',new=AsyncMock(return_value={'results':[]})), \
         patch('app.geoapify_destinations.httpx.AsyncClient') as client:
        with pytest.raises(HTTPException) as error:
            asyncio.run(overseas_candidates(country_code='jp'))
    assert error.value.status_code==404
    client.assert_not_called()


def test_domestic_country_filter_accepts_existing_domestic_records_without_iso_code():
    assert filter_country([CITIES[0]],'kr')==[CITIES[0]]
