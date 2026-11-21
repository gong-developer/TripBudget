import asyncio
from unittest.mock import AsyncMock, patch

import httpx
from app.destinations import budget_candidates
from app.geoapify_destinations import overseas_candidates, REGIONS, REGION_CACHE
from app.place_names import localize_destination_label


def test_all_providers_start_together():
    async def run():
        domestic_started, overseas_started = asyncio.Event(), asyncio.Event()
        async def domestic():
            domestic_started.set()
            await asyncio.wait_for(overseas_started.wait(), .5)
            return [{'cityName':'국내'}]
        async def overseas():
            overseas_started.set()
            await asyncio.wait_for(domestic_started.wait(), .5)
            return [{'cityName':'해외'}]
        with patch('app.destinations.domestic_budget_candidates',side_effect=domestic), \
             patch('app.destinations.overseas_candidates',side_effect=overseas):
            results=await budget_candidates('all')
        assert [row['cityName'] for row in results]==['국내','해외']
    asyncio.run(run())


def test_region_cache_reuses_api_results_and_refreshes_after_expiry(monkeypatch):
    monkeypatch.setenv('GEOAPIFY_API_KEY','secret-test')
    calls=[]
    def handler(request):
        calls.append(request)
        return httpx.Response(200,json={'features':[{'properties':{
            'name':'Tokyo','country':'Japan','country_code':'jp','lat':35.6,'lon':139.7}}]})
    # Save the real constructor before patching the shared httpx module.
    real_client=httpx.AsyncClient
    async def run():
        with patch('app.geoapify_destinations.random.sample',return_value=[REGIONS[0]]), \
             patch('app.geoapify_destinations.httpx.AsyncClient',side_effect=lambda **kw:real_client(transport=httpx.MockTransport(handler))):
            first=await overseas_candidates(batches=1)
            second=await overseas_candidates(batches=1)
            assert first==second
            assert len(calls)==1
            for key, (_, values) in list(REGION_CACHE.items()):
                REGION_CACHE[key]=(0,values)
            await overseas_candidates(batches=1)
            assert len(calls)==2
    asyncio.run(run())


def test_unregistered_names_need_no_translation_network_wait():
    city={'cityName':'Unknown · Japan','originalName':'Unknown','lat':35,'lng':139,
          'countryCode':'jp','category':'international'}
    with patch('httpx.AsyncClient',side_effect=AssertionError('No translation API')):
        result=asyncio.run(localize_destination_label(city,allow_original=True))
    assert result['originalName']=='Unknown'
    assert result['displayName']=='Unknown · 일본'
    assert result['nameTranslationNotice']
