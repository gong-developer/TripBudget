from unittest.mock import patch
import httpx
import pytest
from fastapi.testclient import TestClient
from app.main import app, EXTERNAL_CITIES

client = TestClient(app)

@pytest.fixture(autouse=True)
def clean_registry():
    EXTERNAL_CITIES.clear()
    yield
    EXTERNAL_CITIES.clear()

@pytest.mark.parametrize("category,key", [("international", "GEOAPIFY_API_KEY")])
def test_missing_provider_key(monkeypatch, category, key):
    monkeypatch.delenv(key, raising=False)
    response = client.get('/api/destinations/search', params={'q':'London','category':category})
    assert response.status_code == 503
    assert key in response.json()['detail']

def test_domestic_search_recommend_and_itinerary(monkeypatch):
    monkeypatch.setenv('TOUR_API_KEY','secret-test')
    monkeypatch.setenv('DEMO_MODE','true')
    with patch('httpx.AsyncClient',side_effect=AssertionError('No attraction lookup during region search')):
        response = client.get('/api/destinations/search?q=강릉&category=domestic')
    assert response.status_code == 200
    cities = response.json()['cities']
    assert len(cities) == 1
    name = cities[0]['cityName']
    response = client.post('/api/recommend', json={'budget':1000000,'category':'domestic','destinationNames':[name]})
    assert response.status_code == 200
    assert response.json()['cities'][0]['cityName'] == name
    response = client.post('/api/generate-itinerary', json={'budget':1000000,'cityName':name,'days':4})
    assert response.status_code == 200
    assert 'DAY 4' in response.json()['text']

def test_international_excludes_korea_and_handles_duplicates(monkeypatch):
    monkeypatch.setenv('GEOAPIFY_API_KEY','secret-test')
    rows=[{'city':'서울','country':'대한민국','country_code':'kr','lat':37,'lon':127},
          {'city':'London','country':'UK','country_code':'gb','lat':51.5,'lon':-0.1}]
    with patch('app.destinations.httpx.AsyncClient', return_value=httpx.AsyncClient(transport=httpx.MockTransport(
            lambda r:httpx.Response(200,json={'results':rows+[rows[1]]})))):
        response=client.get('/api/destinations/search?q=London&category=international')
    assert response.status_code == 200
    assert len(response.json()['cities']) == 1
    assert response.json()['cities'][0]['category'] == 'international'

@pytest.mark.parametrize('status', [403,429,500])
def test_provider_failure_does_not_expose_key(monkeypatch,status):
    monkeypatch.setenv('GEOAPIFY_API_KEY','secret-test')
    with patch('app.destinations.httpx.AsyncClient', return_value=httpx.AsyncClient(transport=httpx.MockTransport(
            lambda r:httpx.Response(status,text='secret-test')))):
        response=client.get('/api/destinations/search?q=London&category=international')
    assert response.status_code == (429 if status==429 else 502)
    assert 'secret-test' not in response.text

def test_expired_search_and_validation():
    assert client.post('/api/recommend',json={'budget':500000,'destinationNames':['expired']}).status_code == 409
    assert client.get('/api/destinations/search?q=a').status_code == 422
    assert client.get('/api/destinations/search?q=London&category=all').status_code == 422

def test_domestic_random_selects_a_region_before_looking_up_sights(monkeypatch):
    monkeypatch.delenv('TOUR_API_KEY', raising=False)
    monkeypatch.setenv('DEMO_MODE','true')
    with patch('httpx.AsyncClient',side_effect=AssertionError('No sight lookup during region selection')):
        response=client.get('/api/destinations/random?category=domestic')
    assert response.status_code == 200
    city=response.json()['city']
    assert city['destinationType']=='region' and city['regionId']
    assert city['recommendedPlaces']==[]
    assert client.post('/api/generate-itinerary',json={'cityName':city['cityName'],'budget':500000,'days':2}).status_code == 200


def test_overseas_budget_uses_live_city_api(monkeypatch):
    monkeypatch.setenv('GEOAPIFY_API_KEY','secret-test')
    payload={'features':[{'properties':{'city':'Lima','country':'Peru','country_code':'pe','lat':-12,'lon':-77}}]}
    with patch('app.geoapify_destinations.httpx.AsyncClient',return_value=httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,json=payload)))):
        response=client.get('/api/destinations/random?budget=100000000&category=international')
    assert response.status_code == 200
    city=response.json()['city']
    assert city['source']=='Geoapify / OpenStreetMap'
    assert city['originalName']=='Lima'
    assert city['countryCode']!='kr'
    assert city['nameLocalized'] is True

def test_random_has_no_catalog_fallback(monkeypatch):
    monkeypatch.delenv('TOUR_API_KEY',raising=False)
    assert client.get('/api/destinations/random?category=domestic').status_code == 200
    monkeypatch.delenv('GEOAPIFY_API_KEY',raising=False)
    assert client.get('/api/destinations/random?category=international').status_code == 503
    assert all(city['category']=='domestic' for city in EXTERNAL_CITIES.values())

@pytest.mark.parametrize('chosen',['domestic','international'])
def test_all_random_selects_category_and_requires_selected_provider_key(monkeypatch,chosen):
    from unittest.mock import AsyncMock
    monkeypatch.setenv('TOUR_API_KEY','test')
    monkeypatch.setenv('GEOAPIFY_API_KEY','test')
    if chosen == 'domestic':
        payload={'response':{'header':{'resultCode':'0000'},'body':{'totalCount':1,'items':{'item':[
            {'title':'관광지','mapy':'36','mapx':'128'}]}}}}
    else:
        payload={'features':[{'properties':{'city':'Lima','country':'Peru','country_code':'pe','lat':-12,'lon':-77}}]}
    with patch('app.destinations.choose_category',return_value=chosen), patch('app.destinations.httpx.AsyncClient',return_value=httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,json=payload)))):
        response=client.get('/api/destinations/random?category=all')
    assert response.status_code == 200
    assert response.json()['city']['category'] == chosen
    monkeypatch.delenv('TOUR_API_KEY' if chosen=='domestic' else 'GEOAPIFY_API_KEY')
    with patch('app.destinations.choose_category',return_value=chosen):
        assert client.get('/api/destinations/random?category=all').status_code == (200 if chosen=='domestic' else 503)
