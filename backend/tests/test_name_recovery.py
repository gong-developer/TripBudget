import asyncio
from unittest.mock import AsyncMock, patch
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.main import app, EXTERNAL_CITIES
from app.place_names import local_names, localize_destination_label


def test_catalog_dictionary_matches_name_country_and_location_without_ai():
    from app.city_catalog import load_city_catalog
    entry=next(row for row in load_city_catalog() if row['originalName']=='Valencia' and row['countryCode']=='es')
    assert local_names({'city':'Valencia','country_code':'es',
                        'lat':entry['lat'],'lon':entry['lng']})==('발렌시아','스페인')


def test_same_name_in_another_country_is_not_used():
    entry={'name':'도시 하나','lat':10,'lng':20}
    with patch('app.place_names.catalog_name_index',return_value=({('xx','sometown'):[entry]},{})):
        assert local_names({'city':'Sometown','country_code':'yy'})[0] is None
        assert local_names({'city':'Sometown','country_code':'xx','lat':50,'lon':60})[0] is None


def test_duplicate_names_require_unambiguous_matching_location():
    rows=[{'name':'도시 하나','lat':10,'lng':20},{'name':'도시 둘','lat':30,'lng':40}]
    with patch('app.place_names.catalog_name_index',return_value=({('xx','sometown'):rows},{})):
        assert local_names({'city':'Sometown','country_code':'xx'})[0] is None
        assert local_names({'city':'Sometown','country_code':'xx','lat':30,'lon':40})[0]=='도시 둘'


def test_translation_failure_preserves_original_and_does_not_replace_city():
    city={'cityName':'Unknown · Japan','originalName':'Unknown','lat':35,'lng':139,
          'countryCode':'jp','category':'international'}
    with patch('app.place_names.korean_names',new=AsyncMock(side_effect=HTTPException(503,'translation failed'))):
        result=asyncio.run(localize_destination_label(city,allow_original=True))
    assert result['cityName']==city['cityName']
    assert result['lat']==35 and result['lng']==139
    assert result['originalName']=='Unknown'
    assert result['displayName']=='Unknown · 일본'
    assert result['nameTranslationNotice']
    assert result['nameLocalized'] is False


def test_recommendation_succeeds_if_translation_service_fails():
    city={'cityName':'Unknown · Japan','originalName':'Unknown','lat':35,'lng':139,
          'countryCode':'jp','category':'international','recommendedPlaces':['Unknown']}
    EXTERNAL_CITIES.clear()
    try:
        with patch('app.main.random_destination',new=AsyncMock(return_value=city)), \
             patch('app.place_names.korean_names',new=AsyncMock(side_effect=HTTPException(503,'translation failed'))) as translate:
            client=TestClient(app)
            response=client.get('/api/destinations/random?category=international')
            assert response.status_code==200
            selected=response.json()['city']
            assert selected['nameTranslationNotice']
            assert selected['cityName']==city['cityName']
            repeated=client.post('/api/destinations/display-name',json={
                'cityName':city['cityName'],'lat':35,'lng':139,'countryCode':'jp'})
            assert repeated.status_code==200
            assert repeated.json()['originalName']=='Unknown'
            translate.assert_awaited_once()
    finally:
        EXTERNAL_CITIES.clear()
