import asyncio
from concurrent.futures import ThreadPoolExecutor
import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.middleware.cors import CORSMiddleware
from app.protection import APIProtectionMiddleware, reserve
from app.storage import DestinationStore
from app.web import install_web


def protected_app():
    app=FastAPI()
    app.add_middleware(APIProtectionMiddleware)
    app.add_middleware(CORSMiddleware,allow_origins=['https://example.com'])
    @app.post('/api/generate-itinerary')
    async def generate():
        return {'ok':True}
    @app.get('/api/health')
    def health():
        return {'status':'ok'}
    return app


def test_rate_limit_cannot_be_bypassed_by_forwarded_header_and_preserves_cors(monkeypatch):
    monkeypatch.setenv('AI_REQUESTS_PER_MINUTE','1')
    client=TestClient(protected_app())
    assert client.post('/api/generate-itinerary',headers={'X-Forwarded-For':'1.1.1.1'}).status_code==200
    response=client.post('/api/generate-itinerary',headers={'X-Forwarded-For':'2.2.2.2','Origin':'https://example.com'})
    assert response.status_code==429
    assert int(response.headers['retry-after'])>0
    assert response.headers['access-control-allow-origin']=='https://example.com'
    assert response.headers['x-content-type-options']=='nosniff'
    assert client.get('/api/health').status_code==200


def test_daily_cap_is_persistent_across_clients_and_resets_next_day(monkeypatch):
    monkeypatch.setenv('AI_REQUESTS_PER_DAY','1')
    assert reserve('/api/generate-itinerary','one',86401)==0
    assert reserve('/api/generate-itinerary','two',86402)>0
    assert reserve('/api/generate-itinerary','two',172801)==0


def test_concurrent_quota_reservations_never_exceed_cap(monkeypatch):
    monkeypatch.setenv('AI_REQUESTS_PER_DAY','3')
    with ThreadPoolExecutor(max_workers=6) as pool:
        results=list(pool.map(lambda i:reserve('/api/generate-itinerary',str(i),86401),range(12)))
    assert results.count(0)==3


def test_body_limit_prevents_handler_execution(monkeypatch):
    monkeypatch.setenv('API_MAX_BODY_BYTES','8')
    response=TestClient(protected_app()).post('/api/generate-itinerary',content=b'x'*9)
    assert response.status_code==413


def test_unavailable_limit_store_fails_closed_without_breaking_health(tmp_path,monkeypatch):
    monkeypatch.setenv('API_LIMIT_DB',str(tmp_path))
    client=TestClient(protected_app())
    assert client.post('/api/generate-itinerary').status_code==503
    assert client.get('/api/health').status_code==200


def test_concurrent_capacity_is_released_after_response(monkeypatch):
    monkeypatch.setenv('API_MAX_CONCURRENT','1')
    async def run():
        app=protected_app();started=asyncio.Event();release=asyncio.Event()
        @app.get('/api/slow')
        async def slow():
            started.set();await release.wait();return {'ok':True}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='http://test') as client:
            first=asyncio.create_task(client.get('/api/slow'))
            await asyncio.wait_for(started.wait(),1)
            try:
                assert (await client.post('/api/generate-itinerary')).status_code==503
            finally:
                release.set()
            assert (await first).status_code==200
            assert (await client.post('/api/generate-itinerary')).status_code==200
    asyncio.run(run())


def test_destinations_survive_new_store_and_keep_original_identity():
    first=DestinationStore()
    city={'cityName':'테스트 도시','lat':35,'lng':129,'category':'international'}
    first[city['cityName']]=city
    second=DestinationStore()
    assert second[city['cityName']]==city
    second['다른 도시']={**city,'cityName':'다른 도시'}
    first.move_to_end(city['cityName'])
    assert second.popitem(last=False)[0]=='다른 도시'
    assert list(first)==['테스트 도시']


def test_production_build_is_served_on_api_origin(tmp_path,monkeypatch):
    dist=tmp_path/'dist';(dist/'assets').mkdir(parents=True)
    (dist/'index.html').write_text('<html>TripBudget</html>',encoding='utf-8')
    (dist/'assets'/'app-123.js').write_text('console.log(1)',encoding='utf-8')
    monkeypatch.setenv('FRONTEND_DIST',str(dist))
    app=protected_app();install_web(app);client=TestClient(app)
    assert 'TripBudget' in client.get('/').text
    assert client.get('/').headers['cache-control']=='no-cache'
    assert 'immutable' in client.get('/assets/app-123.js').headers['cache-control']
    assert client.get('/api/health').json()=={'status':'ok'}
    assert client.get('/assets/../../secret.env').status_code==404


def test_empty_storage_overrides_still_use_writable_data_directory(tmp_path,monkeypatch):
    from app.storage import data_path
    monkeypatch.setenv('APP_DATA_DIR',str(tmp_path))
    monkeypatch.setenv('DESTINATION_DB','')
    assert data_path('DESTINATION_DB','destinations.sqlite3')==tmp_path/'destinations.sqlite3'


def test_extreme_dates_are_rejected_before_cost_calculation():
    from app.main import app,CITIES
    response=TestClient(app).post('/api/estimate',json={'cityName':CITIES[0]['cityName'],
                                                     'departureDate':'9999-12-31','days':14})
    assert response.status_code==422
