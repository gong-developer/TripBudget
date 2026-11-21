import asyncio
import json
from unittest.mock import AsyncMock,patch
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.main import app,EXTERNAL_CITIES,CITIES,ItineraryRequest
from app.geoapify_destinations import parse_city
from app.overseas_regions import as_overseas_region,overseas_sights
from app.travel_services import nearby_places
from app.compact_itinerary import plan_input
from app.itinerary_context import prepare_itinerary
from app.domestic_regions import region_history
from plan_fixtures import quality_response


def tokyo():
    return parse_city({'properties':{'name':'Tokyo','country':'Japan','country_code':'jp',
                                  'lat':35.68,'lon':139.76,'place_id':'city-node'}})


def area():
    return {'name':'Tokyo','country_code':'jp','lat':35.68,'lon':139.76,'result_type':'city',
            'place_id':'city-boundary','bbox':{'lon1':139.6,'lat1':35.6,'lon2':139.9,'lat2':35.9}}


def sight(name='센소지',code='jp',lat=35.71,lon=139.79,boundary='city-boundary'):
    return {'properties':{'name':name,'country_code':code,'lat':lat,'lon':lon,
                          'city_place_id':boundary,'place_id':name,'categories':['tourism.sights']}}


def test_overseas_recommendations_are_regions_with_no_preset_sights():
    city=tokyo()
    assert city['destinationType']=='region' and len(city['regionId'])<=32
    assert city['recommendedPlaces']==[]
    assert city['displayName']=='도쿄 · 일본'
    assert as_overseas_region(city)['regionId']==city['regionId']
    data=plan_input(city,ItineraryRequest(cityName=city['cityName'],budget=1000000))
    assert data['destinationType']=='region' and data['regionId']==city['regionId']
    assert data['originalName']=='Tokyo' and data['places']==[]


def test_sights_use_verified_city_boundary_and_exclude_other_cities_and_countries():
    calls=[]
    async def request(path,params):
        calls.append((path,params))
        if 'geocode' in path:
            assert params['type']=='city' and params['filter']=='countrycode:jp'
            return {'results':[area()]}
        assert params['filter']=='place:city-boundary'
        return {'features':[sight(),sight(),sight('서울','kr'),sight('다른 도시',boundary='other-city'),
                            sight('너무 먼 곳',lat=40),sight('경계 밖',lat=35.58),
                            sight('명소 아님')|{'properties':{**sight()['properties'],'result_type':'city'}}]}
    with patch('app.overseas_regions.geo_request',side_effect=request):
        result=asyncio.run(overseas_sights(tokyo()))
    assert len(calls)==2
    assert [p['name'] for p in result['places']]==['센소지']


@pytest.mark.parametrize('rows',[[],[{**area(),'country_code':'kr'}],[{**area(),'lat':1}],[{**area(),'result_type':'country'}]])
def test_missing_or_wrong_boundary_never_expands_to_a_nearby_country_or_city(rows):
    with patch('app.overseas_regions.geo_request',new=AsyncMock(return_value={'results':rows})) as request:
        with pytest.raises(HTTPException) as error:
            asyncio.run(overseas_sights(tokyo()))
    assert error.value.status_code==404
    assert request.await_count==1


def test_nearby_and_itinerary_share_the_selected_overseas_region():
    city=tokyo()
    data=plan_input(city,ItineraryRequest(cityName=city['cityName'],budget=1000000,days=1))
    places=[{'name':f'명소 {i}','originalName':f'명소 {i}','lat':35.68+i*.001,'lng':139.76} for i in range(4)]
    provider=AsyncMock(return_value={'places':places,'source':'Geoapify / OpenStreetMap'})
    async def run():
        assert (await nearby_places(city))['places']==places
        result=await prepare_itinerary(data)
        assert len(result['places'])==4
        assert all(p['name']!='Tokyo' for p in result['places'])
    with patch('app.overseas_regions.overseas_sights',new=provider), \
         patch('app.itinerary_context.geo_request',new=AsyncMock()) as fallback:
        asyncio.run(run())
    assert provider.call_args_list[0].args[0]['regionId']==provider.call_args_list[1].args[0]['regionId']
    fallback.assert_not_awaited()


def test_provider_failure_does_not_replace_region_sights_with_preset_names():
    data=plan_input(tokyo(),ItineraryRequest(cityName=tokyo()['cityName'],budget=1000000))
    with patch('app.overseas_regions.overseas_sights',new=AsyncMock(side_effect=HTTPException(429,'사용 한도'))):
        with pytest.raises(HTTPException) as error:asyncio.run(prepare_itinerary(data))
    assert error.value.status_code==429


def test_region_metadata_survives_restore_and_overrides_same_named_sample_city(monkeypatch):
    monkeypatch.setenv('DEMO_MODE','false')
    monkeypatch.setenv('GEMINI_API_KEY','test')
    city=as_overseas_region({**next(row for row in CITIES if row['cityName']=='도쿄 · 일본'),'countryCode':'jp','originalName':'Tokyo'})
    client=TestClient(app)
    EXTERNAL_CITIES.clear()
    try:
        restored=client.post('/api/destinations/restore',json={'cities':[city]}).json()['cities'][0]
        assert restored['regionId']==city['regionId'] and restored['recommendedPlaces']==[]
        with patch('app.main.compact_plan',new=AsyncMock(return_value='1일차 일정')) as generate:
            response=client.post('/api/generate-itinerary',json={'cityName':city['cityName'],'budget':1000000,'days':1})
        assert response.status_code==200
        selected=generate.call_args.args[0]
        assert selected['destinationType']=='region' and selected['recommendedPlaces']==[]
        legacy={**city,'recommendedPlaces':['옛 명소']}
        legacy.pop('destinationType')
        history=region_history([legacy])
        assert history[0]['destinationType']=='region' and history[0]['recommendedPlaces']==[]
    finally:EXTERNAL_CITIES.clear()
