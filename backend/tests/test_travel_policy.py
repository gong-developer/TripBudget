import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from app.main import app, CITIES, EXTERNAL_CITIES
from app.travel_policy import EXCLUDED_COUNTRIES, allowed_destination
from app.countries import country_boundaries, filter_country
from app.geoapify_destinations import parse_city

client = TestClient(app)


def blocked_city(code='kp'):
    return {**CITIES[0], 'cityName':f'제외 지역 · {EXCLUDED_COUNTRIES[code][0]}',
            'category':'international','countryCode':code,'destinationType':'region'}


@pytest.mark.parametrize('code', list(EXCLUDED_COUNTRIES))
def test_excluded_country_never_enters_map_provider_or_country_search(code):
    assert not allowed_destination(blocked_city(code))
    assert code not in {f['properties']['code'] for f in country_boundaries()['features']}
    assert parse_city({'properties':{'name':'Excluded city','country':'Excluded country',
           'country_code':code,'lat':35,'lon':130}}) is None
    with patch('app.main.random_destination',AsyncMock()) as lookup:
        response=client.get('/api/destinations/random',params={'countryCode':code})
        assert response.status_code==422 and '여행금지' in response.json()['detail']
        lookup.assert_not_awaited()


def test_legacy_records_without_country_codes_are_also_filtered():
    legacy=blocked_city('af');legacy.pop('countryCode')
    assert filter_country([legacy,CITIES[0]],None)==[CITIES[0]]
    # Partial-country restrictions must not be mistaken for nationwide bans.
    assert allowed_destination({'countryCode':'ph','category':'international'})
    assert allowed_destination({'countryCode':'jp','category':'international'})


def test_previous_registry_results_cannot_reenter_comparison():
    city=blocked_city()
    EXTERNAL_CITIES[city['cityName']]=city
    with patch('app.travel_features.budget_candidates',AsyncMock(return_value=[CITIES[0],city])):
        response=client.post('/api/destinations/compare',json={'budget':10000000})
    result=json.loads(response.text.splitlines()[-1])
    assert result['type']=='result'
    assert all(item.get('countryCode')!='kp' for item in result['cities'])


def test_saved_plan_and_direct_ai_or_sight_requests_cannot_bypass_exclusion():
    city=blocked_city()
    EXTERNAL_CITIES[city['cityName']]=city
    with patch('app.main.compact_plan',AsyncMock()) as generate, \
         patch('app.travel_features.nearby_places',AsyncMock()) as nearby:
        assert client.post('/api/generate-itinerary',json={'cityName':city['cityName'],'budget':1000000}).status_code==422
        assert client.post('/api/nearby-places',json={'cityName':city['cityName']}).status_code==422
        saved={key:city[key] for key in ('cityName','lat','lng','category','countryCode')}
        assert client.post('/api/destinations/restore',json={'cities':[saved]}).status_code==422
        generate.assert_not_awaited()
        nearby.assert_not_awaited()


def test_free_text_search_results_are_filtered_before_returning():
    with patch('app.main.search_destinations',AsyncMock(return_value=[blocked_city(),CITIES[0]])):
        response=client.get('/api/destinations/search',params={'q':'여행지','category':'international'})
    assert response.status_code==200
    assert [row['cityName'] for row in response.json()['cities']]==[CITIES[0]['cityName']]
