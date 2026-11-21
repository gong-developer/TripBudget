import asyncio
from unittest.mock import AsyncMock, patch
import httpx
import pytest
from fastapi import HTTPException
from app.travel_services import nearby_places, place_details, daily_route, geo_request, CACHE

CITY={'cityName':'Paris · France','lat':48.85,'lng':2.35,'countryCode':'fr'}


def poi(name='명소',lat=48.85,lon=2.35):
    return {'properties':{'name':name,'lat':lat,'lon':lon,'place_id':name,
            'formatted':'주소','opening_hours':'Mo-Fr 09:00-18:00','website':'https://example.com'}}


def test_nearby_places_deduplicate_and_exclude_bad_coordinates():
    data={'features':[poi(),poi(),poi('잘못된 곳',999)]}
    with patch('app.travel_services.geo_request',new=AsyncMock(return_value=data)):
        result=asyncio.run(nearby_places(CITY))
    assert len(result['places'])==1
    assert result['places'][0]['lat']==48.85


def test_place_details_absent_fields_and_unsafe_links_are_not_fabricated():
    data=poi();data['properties'].update(website='javascript:alert(1)',opening_hours=None)
    with patch('app.travel_services.geo_request',new=AsyncMock(return_value={'features':[data]})):
        result=asyncio.run(place_details('identifier',48,2))
    assert result['website'] is None and result['openingHours'] is None


def test_nearby_uses_provider_korean_and_retains_unregistered_native_names():
    english=poi('Central Park')
    english['properties']['name_international']={'ko':'센트럴 파크'}
    native=poi('中央公園',48.86)
    native['properties']['name_international']={'en':'Central Park'}
    korean=poi('현지 공원',48.87)
    with patch('app.travel_services.geo_request',new=AsyncMock(return_value={'features':[english,native,korean]})):
        result=asyncio.run(nearby_places(CITY))
    assert [place['name'] for place in result['places']]==['센트럴 파크','中央公園','현지 공원']
    assert result['places'][0]['originalName']=='Central Park'
    assert result['places'][1]['originalName']=='中央公園'
    assert result['places'][1]['placeId']=='中央公園'
    assert result['places'][0]['nameTranslated'] is False
    assert result['places'][0]['nameSource']=='provider'


def test_details_discard_bad_provider_korean_without_machine_translation():
    feature=poi('Lake Geneva')
    feature['properties']['name_international']={'ko':'숙박 약관'}
    with patch('app.travel_services.geo_request',new=AsyncMock(return_value={'features':[feature]})):
        result=asyncio.run(place_details('Lake Geneva',48,2))
    assert result['name']=='Lake Geneva' and result['originalName']=='Lake Geneva'
    assert result['address']=='주소' and result['placeId']=='Lake Geneva'


def test_legacy_machine_place_is_replaced_by_original_without_losing_identity():
    from app.travel_services import localize_places
    place={'name':'전체메뉴','originalName':'Seomyeon Shopping District','nameTranslated':True,'lat':35,'lng':129,'placeId':'one'}
    result=asyncio.run(localize_places([place]))[0]
    assert result['name']=='Seomyeon Shopping District'
    assert result['placeId']=='one' and result['lat']==35


def test_daily_route_uses_actual_geometry_and_returns_map_coordinate_order():
    async def request(path,params):
        if path=='/v2/places':
            return {'features':[]}
        if 'geocode' in path:
            offset=.01 if params['text'].startswith('둘') else 0
            return {'results':[{'lat':48.85+offset,'lon':2.35,'country_code':'fr','result_type':'amenity'}]}
        assert params['waypoints']=='48.85,2.35|48.86,2.35'
        assert params['mode']=='walk'
        return {'features':[{'geometry':{'type':'MultiLineString','coordinates':[[[2.35,48.85],[2.35,48.86]]]},
                             'properties':{'distance':1200,'time':900}}]}
    with patch('app.travel_services.geo_request',side_effect=request):
        route=asyncio.run(daily_route(CITY,['하나','둘'],'walk'))
    assert route['lines']==[[[48.85,2.35],[48.86,2.35]]]
    assert route['distance']==1200 and route['duration']==900


@pytest.mark.parametrize('row',[
    {'lat':1,'lon':1,'country_code':'fr','result_type':'amenity'},
    {'lat':48.85,'lon':2.35,'country_code':'jp','result_type':'amenity'},
    {'lat':48.85,'lon':2.35,'country_code':'fr','result_type':'city'},
    {'lat':48.85,'lon':2.35,'country_code':'fr','result_type':'amenity','rank':{'confidence':.2}},
])
def test_wrong_or_ambiguous_locations_do_not_produce_fake_routes(row):
    with patch('app.travel_services.nearby_places',new=AsyncMock(return_value={'places':[]})), \
         patch('app.travel_services.geo_request',new=AsyncMock(return_value={'results':[row]})) as request:
        with pytest.raises(HTTPException) as error:
            asyncio.run(daily_route(CITY,['하나','둘'],'walk'))
    assert error.value.status_code==404
    assert all('routing' not in call.args[0] for call in request.await_args_list)


def test_geo_requests_cache_success_and_safe_errors(monkeypatch):
    monkeypatch.setenv('GEOAPIFY_API_KEY','secret-test')
    real_client=httpx.AsyncClient
    calls=[]
    def handler(request):
        calls.append(request)
        return httpx.Response(200,json={'features':[]})
    async def run():
        with patch('app.travel_services.httpx.AsyncClient',side_effect=lambda **kw:real_client(transport=httpx.MockTransport(handler))):
            await geo_request('/v2/places',{'limit':12})
            await geo_request('/v2/places',{'limit':12})
    asyncio.run(run())
    assert len(calls)==1


def test_missing_key_and_malformed_provider_response(monkeypatch):
    monkeypatch.delenv('GEOAPIFY_API_KEY',raising=False)
    with pytest.raises(HTTPException) as error:
        asyncio.run(geo_request('/v2/places',{}))
    assert error.value.status_code==503
    with patch('app.travel_services.geo_request',new=AsyncMock(return_value={'features':None})):
        with pytest.raises(HTTPException) as error:
            asyncio.run(nearby_places(CITY))
    assert error.value.status_code==502


def test_zero_length_snapped_route_is_not_presented_as_valid_travel():
    async def request(path, params):
        if 'geocode' in path:
            lat=48.85 if params['text'].startswith('하나') else 48.86
            return {'results':[{'lat':lat,'lon':2.35,'result_type':'amenity'}]}
        return {'features':[{'geometry':{'type':'LineString','coordinates':[[2.35,48.85],[2.35,48.85]]},
                             'properties':{'distance':0,'time':0}}]}
    with patch('app.travel_services.nearby_places',new=AsyncMock(return_value={'places':[]})), \
         patch('app.travel_services.geo_request',side_effect=request):
        with pytest.raises(HTTPException) as error:
            asyncio.run(daily_route(CITY,['하나','둘'],'walk'))
    assert error.value.status_code==404
