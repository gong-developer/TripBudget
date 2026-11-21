import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from app import unsplash_photos as photos
from app import destination_photos as covers

CITY={'cityName':'Tokyo · 일본','originalName':'Tokyo','countryCode':'jp','lat':35.68,'lng':139.76}


def detail(latitude=35.68):
    return {'id':'tokyo-photo','location':{'position':{'latitude':latitude,'longitude':139.76}},
            'urls':{'regular':'https://images.unsplash.com/test?ixid=preserve-me'},
            'links':{'html':'https://unsplash.com/photos/tokyo-photo',
                     'download_location':'https://api.unsplash.com/photos/tokyo-photo/download?ixid=tracking'},
            'user':{'name':'Photographer','links':{'html':'https://unsplash.com/@photographer'}},
            'alt_description':'Tokyo skyline'}


def install_transport(monkeypatch,handler):
    real=httpx.AsyncClient
    monkeypatch.setattr(photos.httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(handler),headers=kw.get('headers')))
    monkeypatch.setenv('UNSPLASH_ACCESS_KEY','private-test-key')


def test_verified_cover_preserves_hotlink_attributes_and_tracks_selection(monkeypatch):
    calls=[]
    def handler(request):
        calls.append(request)
        assert request.headers['Authorization']=='Client-ID private-test-key'
        assert 'private-test-key' not in str(request.url)
        if request.url.path=='/search/photos':
            assert request.url.params['query']=='Tokyo Japan'
            return httpx.Response(200,json={'results':[{'id':'tokyo-photo'}]})
        if request.url.path.endswith('/download'):
            assert request.url.params['ixid']=='tracking'
            return httpx.Response(200,json={})
        return httpx.Response(200,json=detail())
    install_transport(monkeypatch,handler)
    result=asyncio.run(photos.unsplash_photo(CITY))
    assert result['url']=='https://images.unsplash.com/test?ixid=preserve-me'
    assert result['source']=='Unsplash'
    assert 'utm_source=triproulette' in result['authorUrl']
    assert 'utm_medium=referral' in result['sourceUrl']
    assert 'private-test-key' not in str(result)
    assert len(calls)==3


def test_unrelated_location_is_never_used_or_tracked(monkeypatch):
    def handler(request):
        assert not request.url.path.endswith('/download')
        return httpx.Response(200,json={'results':[{'id':'tokyo-photo'}]} if request.url.path=='/search/photos' else detail(30))
    install_transport(monkeypatch,handler)
    assert asyncio.run(photos.unsplash_photo(CITY)) is None


@pytest.mark.parametrize('status',[401,403,429,503])
def test_errors_fall_back_without_exposing_credentials_and_quota_backs_off(monkeypatch,status):
    requests=[]
    def handler(request):
        requests.append(request)
        return httpx.Response(status,json={'errors':['private-test-key']})
    install_transport(monkeypatch,handler)
    async def run():
        with patch.object(covers,'commons_photo',AsyncMock(return_value={'source':'Commons'})):
            assert await covers.lookup_photo(CITY)=={'source':'Commons'}
            if status in (401,403,429):
                assert await covers.lookup_photo(CITY)=={'source':'Commons'}
    asyncio.run(run())
    assert len(requests)==1


def test_domestic_does_not_use_unsplash():
    async def run():
        with patch.object(covers,'tour_photo',AsyncMock(return_value={'source':'TourAPI'})), \
             patch.object(photos,'unsplash_photo',AsyncMock()) as lookup:
            assert await covers.lookup_photo({**CITY,'countryCode':'kr','regionId':'region'})=={'source':'TourAPI'}
            lookup.assert_not_awaited()
    asyncio.run(run())


def test_location_names_need_both_city_and_country_when_coordinates_absent():
    assert photos.matching_location({'location':{'city':'Tokyo','country':'Japan'}},CITY,'Tokyo','Japan')
    assert not photos.matching_location({'location':{'city':'Tokyo','country':'United States'}},CITY,'Tokyo','Japan')
    assert not photos.matching_location({'description':'Tokyo skyline'},CITY,'Tokyo','Japan')


def test_missing_key_never_calls_provider():
    with patch.object(photos.httpx,'AsyncClient') as client:
        assert asyncio.run(photos.unsplash_photo(CITY)) is None
        client.assert_not_called()


def test_search_name_does_not_substitute_nearby_district_for_selected_city():
    rows=[{'name':'아사쿠사','originalName':'Asakusa','countryCode':'jp','lat':35.68,'lng':139.76},
          {'name':'도쿄','originalName':'Tokyo','countryCode':'jp','lat':35.69,'lng':139.69}]
    with patch('app.city_catalog.load_city_catalog',return_value=rows):
        assert photos.search_name({**CITY,'originalName':'도쿄도'})=='Tokyo'
