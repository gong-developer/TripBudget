import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient
from app import destination_photos as photos
from app.main import app, CITIES

CITY = {'cityName':'Paris · 프랑스','originalName':'Paris','lat':48.8566,'lng':2.3522,'countryCode':'fr'}


@pytest.fixture(autouse=True)
def clear_photos():
    photos.CACHE.clear()
    photos.INFLIGHT.clear()


@pytest.mark.parametrize('latitude,license_name,url,expected',[
    (48.8566,'CC BY-SA 4.0','https://upload.wikimedia.org/photo.jpg',True),
    (35,'CC BY-SA 4.0','https://upload.wikimedia.org/photo.jpg',False),
    (48.8566,'All rights reserved','https://upload.wikimedia.org/photo.jpg',False),
    (48.8566,'CC BY-SA 4.0','https://evil.example/photo.jpg',False),
])
def test_photo_checks_location_license_and_hosts(monkeypatch,latitude,license_name,url,expected):
    calls=[]
    def handler(request):
        calls.append(request)
        if request.url.host == 'en.wikipedia.org':
            pages={'1':{'pageimage':'Paris.jpg','coordinates':[{'lat':latitude,'lon':2.3522}]}}
        else:
            pages={'2':{'imageinfo':[{'mime':'image/jpeg','thumburl':url,
                'descriptionurl':'https://commons.wikimedia.org/wiki/File:Paris.jpg',
                'extmetadata':{'Artist':{'value':'<a href="x">Photographer</a>'},
                               'LicenseShortName':{'value':license_name}}}]}}
        return httpx.Response(200,json={'query':{'pages':pages}})
    real_client=httpx.AsyncClient
    monkeypatch.setattr(photos.httpx,'AsyncClient',lambda **kwargs:real_client(transport=httpx.MockTransport(handler)))
    result=asyncio.run(photos.lookup_photo(CITY))
    assert bool(result) == expected
    if result:
        assert result['author']=='Photographer'
        assert result['sourceUrl'].startswith('https://commons.wikimedia.org/')
    if latitude==35:assert all(call.url.host=='en.wikipedia.org' for call in calls)


def test_concurrent_photos_share_lookup_and_cache_success():
    async def run():
        lookup=AsyncMock(return_value={'url':'photo'})
        with patch.object(photos,'lookup_photo',lookup):
            first,second=await asyncio.gather(photos.destination_photo(CITY),photos.destination_photo(CITY))
            assert first==second==await photos.destination_photo(CITY)
        lookup.assert_awaited_once()
    asyncio.run(run())


def test_provider_failure_is_optional_and_briefly_cached():
    async def run():
        lookup=AsyncMock(side_effect=httpx.ConnectError('unavailable'))
        with patch.object(photos,'lookup_photo',lookup):
            assert await photos.destination_photo(CITY) is None
            assert await photos.destination_photo(CITY) is None
        lookup.assert_awaited_once()
        assert next(iter(photos.CACHE.values()))[0] < photos.time.monotonic()+301
    asyncio.run(run())


def test_photo_endpoint_requires_registered_city():
    client=TestClient(app)
    with patch.object(photos,'destination_photo',AsyncMock(return_value=None)) as lookup:
        assert client.get('/api/destination-photo',params={'cityName':'unknown'}).status_code==404
        response=client.get('/api/destination-photo',params={'cityName':CITIES[0]['cityName']})
        assert response.status_code==200 and response.json()=={'photo':None}
        lookup.assert_awaited_once()


def test_domestic_prefers_tourapi_and_only_falls_back_when_needed():
    city={**CITY,'category':'domestic','countryCode':'kr','regionId':'region'}
    async def run():
        with patch.object(photos,'tour_photo',AsyncMock(return_value={'source':'TourAPI'})) as tour, \
             patch.object(photos,'commons_photo',AsyncMock(return_value={'source':'Commons'})) as commons:
            assert await photos.lookup_photo(city)=={'source':'TourAPI'}
            commons.assert_not_awaited()
            tour.return_value=None
            assert await photos.lookup_photo(city)=={'source':'Commons'}
            commons.assert_awaited_once()
    asyncio.run(run())


@pytest.mark.parametrize('license_code,host,valid',[
    ('Type1','tong.visitkorea.or.kr',True),
    ('Type3','tong.visitkorea.or.kr',False),
    ('Type1','evil.example',False),
])
def test_tourapi_photo_uses_verified_sights_and_explicit_license(monkeypatch,license_code,host,valid):
    def handler(request):
        assert request.url.params['contentId']=='123'
        assert 'subImageYN' not in request.url.params
        row={'originimgurl':f'http://{host}/photo.jpg','cpyrhtDivCd':license_code}
        return httpx.Response(200,json={'response':{'header':{'resultCode':'0000'},'body':{'items':{'item':[row]}}}})
    real_client=httpx.AsyncClient
    monkeypatch.setattr(photos.httpx,'AsyncClient',lambda **kw:real_client(transport=httpx.MockTransport(handler)))
    sight={'name':'지역 안의 명소','contentId':'123'}
    with patch('app.domestic_sights.domestic_sights',AsyncMock(return_value={'places':[sight]})) as lookup:
        result=asyncio.run(photos.tour_photo(CITY))
    lookup.assert_awaited_once_with(CITY,limit=12)
    assert bool(result)==valid
    if result:
        assert result['url']=='https://tong.visitkorea.or.kr/photo.jpg'
        assert result['subjectType']=='sight' and result['title']==sight['name']
        assert result['license']=='공공누리 제1유형'


def test_korean_overseas_name_resolves_through_english_counterpart(monkeypatch):
    calls=[]
    def handler(request):
        calls.append(request.url.host)
        if request.url.host=='ko.wikipedia.org':
            assert request.url.params['titles']=='도쿄도'
            pages={'1':{'title':'도쿄도','langlinks':[{'lang':'en','*':'Tokyo'}]}}
        elif request.url.host=='en.wikipedia.org':
            assert request.url.params['titles']=='Tokyo'
            pages={'2':{'pageimage':'Tokyo.jpg','coordinates':[{'lat':35.68,'lon':139.76}]}}
        else:
            pages={'3':{'imageinfo':[{'mime':'image/jpeg','url':'https://upload.wikimedia.org/Tokyo.jpg',
                    'descriptionurl':'https://commons.wikimedia.org/wiki/File:Tokyo.jpg',
                    'extmetadata':{'LicenseShortName':{'value':'KOGL Type 1'}}}]}}
        return httpx.Response(200,json={'query':{'pages':pages}})
    real_client=httpx.AsyncClient
    monkeypatch.setattr(photos.httpx,'AsyncClient',lambda **kw:real_client(transport=httpx.MockTransport(handler)))
    city={'cityName':'도쿄도 · 일본','originalName':'도쿄도','lat':35.68,'lng':139.76,'countryCode':'jp'}
    result=asyncio.run(photos.lookup_photo(city))
    assert result['url'].endswith('Tokyo.jpg')
    assert calls==['ko.wikipedia.org','en.wikipedia.org','commons.wikimedia.org']


def test_ambiguous_name_uses_nearby_matching_city_and_rejects_other_places(monkeypatch):
    def handler(request):
        if request.url.host=='commons.wikimedia.org':
            assert request.url.params['titles']=='File:Bata.jpg'
            pages={'3':{'imageinfo':[{'mime':'image/jpeg','url':'https://upload.wikimedia.org/Bata.jpg',
                    'descriptionurl':'https://commons.wikimedia.org/wiki/File:Bata.jpg',
                    'extmetadata':{'LicenseShortName':{'value':'CC BY 4.0'}}}]}}
        elif request.url.params.get('generator')=='geosearch':
            pages={
                '1':{'title':'Other city','pageimage':'wrong.jpg','coordinates':[{'lat':1.85,'lon':9.76}]},
                '2':{'title':'Bata, Equatorial Guinea','pageimage':'Bata.jpg','coordinates':[{'lat':1.85,'lon':9.76}]},
            }
        else:
            pages={'0':{'title':'Bata','pageprops':{'disambiguation':''}}}
        return httpx.Response(200,json={'query':{'pages':pages}})
    real_client=httpx.AsyncClient
    monkeypatch.setattr(photos.httpx,'AsyncClient',lambda **kw:real_client(transport=httpx.MockTransport(handler)))
    city={'cityName':'Bata · 적도 기니','originalName':'Bata','lat':1.85,'lng':9.76,'countryCode':'gq'}
    assert asyncio.run(photos.lookup_photo(city))['url'].endswith('Bata.jpg')
