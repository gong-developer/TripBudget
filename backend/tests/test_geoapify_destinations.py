import asyncio
from unittest.mock import patch
import httpx
import pytest
from fastapi import HTTPException
from app.geoapify_destinations import overseas_candidates, parse_city


def feature(name='Tokyo', code='jp', lat=35.6, lon=139.7):
    return {'properties':{'name':name, 'country':'Japan', 'country_code':code,
                          'lat':lat, 'lon':lon, 'place_id':'provider-id'}}


def test_live_batch_queries_and_filters_without_gemini(monkeypatch):
    monkeypatch.setenv('GEOAPIFY_API_KEY','secret-test')
    calls=[]
    def handler(request):
        calls.append(request)
        assert request.url.host=='api.geoapify.com'
        assert request.url.path=='/v2/places'
        assert request.url.params['apiKey']=='secret-test'
        assert request.url.params['categories']=='populated_place.city'
        assert request.url.params['filter'].startswith('rect:')
        assert request.url.params['lang']=='ko'
        assert request.url.params['limit']=='40'
        return httpx.Response(200,json={'features':[
            feature(),feature(),feature('Seoul','kr'),feature('bad','jp',999),
            feature('no country',''),feature('Osaka','jp',34.7,135.5)]})
    with patch('app.geoapify_destinations.httpx.AsyncClient',return_value=httpx.AsyncClient(transport=httpx.MockTransport(handler))):
        cities=asyncio.run(overseas_candidates())
    assert len(calls)==4
    assert {city['displayName'] for city in cities}=={'도쿄 · 일본','오사카 · 일본'}
    assert all(city['source']=='Geoapify / OpenStreetMap' for city in cities)


@pytest.mark.parametrize('status,expected',[(401,502),(403,502),(429,429),(500,502)])
def test_provider_errors_are_safe_and_never_return_catalog(monkeypatch,status,expected):
    monkeypatch.setenv('GEOAPIFY_API_KEY','secret-test')
    with patch('app.geoapify_destinations.httpx.AsyncClient',return_value=httpx.AsyncClient(transport=httpx.MockTransport(
            lambda r:httpx.Response(status,text='secret-test')))):
        with pytest.raises(HTTPException) as error:
            asyncio.run(overseas_candidates(batches=1))
    assert error.value.status_code==expected
    assert 'secret-test' not in error.value.detail


@pytest.mark.parametrize('payload,status',[({'features':[]},503),({},502),({'features':None},502)])
def test_empty_and_malformed_responses_do_not_fall_back(monkeypatch,payload,status):
    monkeypatch.setenv('GEOAPIFY_API_KEY','secret-test')
    with patch('app.geoapify_destinations.httpx.AsyncClient',return_value=httpx.AsyncClient(transport=httpx.MockTransport(
            lambda r:httpx.Response(200,json=payload)))):
        with pytest.raises(HTTPException) as error:
            asyncio.run(overseas_candidates(batches=1))
    assert error.value.status_code==status


def test_missing_key_never_calls_network(monkeypatch):
    monkeypatch.delenv('GEOAPIFY_API_KEY',raising=False)
    with patch('app.geoapify_destinations.httpx.AsyncClient') as client:
        with pytest.raises(HTTPException) as error:
            asyncio.run(overseas_candidates())
    assert error.value.status_code==503
    client.assert_not_called()


def test_geometry_coordinates_used_when_properties_omit_them():
    row=feature()
    del row['properties']['lat'],row['properties']['lon']
    row['geometry']={'coordinates':[139.7,35.6]}
    assert parse_city(row)['lat']==35.6


def test_administrative_region_comes_from_provider_not_query_rectangle():
    row = feature('Sapporo', lat=43.06, lon=141.35)
    row['properties'].update(state='北海道', county='石狩振興局', city='Sapporo', district='石狩振興局')
    assert parse_city(row)['regionName'].startswith('北海道 · 石狩振興局')
    assert parse_city(feature())['regionName'] == '도쿄'


def test_timeout_has_clear_status(monkeypatch):
    monkeypatch.setenv('GEOAPIFY_API_KEY','secret-test')
    def handler(request):
        raise httpx.ReadTimeout('secret-test',request=request)
    with patch('app.geoapify_destinations.httpx.AsyncClient',return_value=httpx.AsyncClient(transport=httpx.MockTransport(handler))):
        with pytest.raises(HTTPException) as error:
            asyncio.run(overseas_candidates(batches=1))
    assert error.value.status_code==504
