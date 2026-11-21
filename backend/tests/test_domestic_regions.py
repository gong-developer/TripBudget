import asyncio
import json
from unittest.mock import AsyncMock, patch
import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.main import app, EXTERNAL_CITIES
from app.domestic_regions import domestic_candidates
from app.domestic_sights import domestic_sights
from app.itinerary_context import prepare_itinerary
from app.compact_itinerary import plan_input
from app.costs import TripOptions


def gangneung():
    return next(city for city in domestic_candidates() if city['originalName']=='강릉시')


def envelope(rows):
    return httpx.Response(200,json={'response':{'header':{'resultCode':'0000'},'body':{'items':{'item':rows}}}})


def test_region_catalog_covers_all_provinces_and_no_preset_sights():
    cities=domestic_candidates()
    assert len({city['areaCode'] for city in cities})==17
    assert all(city['recommendedPlaces']==[] and city['countryCode']=='kr' for city in cities)
    assert len(domestic_candidates('강릉'))==1
    assert any(city['originalName']=='서귀포시' for city in cities)


def test_sights_use_selected_district_not_random_pages(monkeypatch):
    monkeypatch.setenv('TOUR_API_KEY','test')
    calls=[]
    def provider(request):
        calls.append(request)
        assert request.url.params['areaCode']=='32'
        if request.url.path.endswith('/areaCode2'):
            return envelope([{'name':'강릉시','code':'1'},{'name':'속초시','code':'5'}])
        assert request.url.params['sigunguCode']=='1'
        return envelope([
            {'title':'경포해변','mapy':'37.8','mapx':'128.9','addr1':'강원특별자치도 강릉시','areacode':'32','sigungucode':'1'},
            {'title':'다른 지역 명소','mapy':'38.2','mapx':'128.6','areacode':'32','sigungucode':'5'},
            {'title':'좌표 오류','mapy':'','mapx':''}])
    with patch('app.domestic_sights.httpx.AsyncClient',return_value=httpx.AsyncClient(transport=httpx.MockTransport(provider))):
        result=asyncio.run(domestic_sights(gangneung()))
    assert len(calls)==2
    assert [place['name'] for place in result['places']]==['경포해변']
    assert result['places'][0]['source']=='한국관광공사 TourAPI'


def test_unresolved_district_never_queries_another_area(monkeypatch):
    monkeypatch.setenv('TOUR_API_KEY','test')
    calls=[]
    def provider(request):
        calls.append(request)
        return envelope([{'name':'속초시','code':'5'}])
    with patch('app.domestic_sights.httpx.AsyncClient',return_value=httpx.AsyncClient(transport=httpx.MockTransport(provider))):
        with pytest.raises(HTTPException) as error:
            asyncio.run(domestic_sights(gangneung()))
    assert error.value.status_code==404 and len(calls)==1


def test_itinerary_fetches_sights_after_region_selection():
    city=gangneung()
    data=plan_input(city,TripOptions(days=2))
    assert data['places']==[] and data['regionId']==city['regionId']
    sights=[{'name':f'실제 명소 {i}','originalName':f'실제 명소 {i}', 'lat':city['lat']+.001*i,
             'lng':city['lng'],'source':'한국관광공사 TourAPI'} for i in range(5)]
    with patch('app.domestic_sights.domestic_sights',new=AsyncMock(return_value={'places':sights})) as provider, \
         patch('app.itinerary_context.geo_request',new=AsyncMock()) as overseas:
        prepared=asyncio.run(prepare_itinerary(data))
    provider.assert_awaited_once()
    overseas.assert_not_awaited()
    assert len(prepared['places'])==5
    assert all(place['name']!=city['originalName'] for place in prepared['places'])


def test_region_restore_retains_identity_and_old_attractions_are_excluded_from_recommendations():
    client=TestClient(app)
    EXTERNAL_CITIES.clear()
    try:
        city=gangneung()
        restored=client.post('/api/destinations/restore',json={'cities':[city]}).json()['cities'][0]
        assert restored['regionId']==city['regionId'] and restored['destinationType']=='region'
        assert restored['recommendedPlaces']==[]
        EXTERNAL_CITIES['예전 명소']={**city,'cityName':'예전 명소','destinationType':'attraction'}
        with patch('app.travel_features.budget_candidates',new=AsyncMock(return_value=[city])):
            response=client.post('/api/destinations/compare',json={'budget':100000000,'category':'domestic'})
        result=json.loads(response.text.splitlines()[-1])
        assert result['type']=='result'
        assert all(row['cityName']!='예전 명소' for row in result['cities'])
    finally:
        EXTERNAL_CITIES.clear()
