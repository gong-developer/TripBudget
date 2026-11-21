import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import httpx
from fastapi import HTTPException
from app import compact_itinerary as plans
from app.main import CITIES, ItineraryRequest
from plan_fixtures import quality_response


@pytest.fixture(autouse=True)
def clear_cache():
    plans.CACHE.clear()
    plans.INFLIGHT.clear()


def test_same_route_coalesces_and_reuses_across_price_changes():
    async def run():
        fake = SimpleNamespace(generate_content_async=AsyncMock(return_value=SimpleNamespace(
            candidates=[SimpleNamespace(finish_reason=1)],
            text=quality_response(3))))
        sdk = SimpleNamespace(GenerativeModel=lambda **kwargs: fake)
        request = ItineraryRequest(cityName=CITIES[0]['cityName'], budget=500000)
        first, second = await asyncio.gather(*[
            plans.compact_plan(CITIES[0], request, sdk, 'test', 'key') for _ in range(2)])
        assert first == second
        changed = request.model_copy(update={'budget':900000, 'people':3, 'hotelPerRoomNight':100000})
        assert await plans.compact_plan(CITIES[0], changed, sdk, 'test', 'key') == first
        fake.generate_content_async.assert_awaited_once()
        payload = json.loads(fake.generate_content_async.call_args.args[0])
        assert 'costEstimate' not in payload and 'budgetKRW' not in payload
        assert fake.generate_content_async.call_args.kwargs['generation_config']['max_output_tokens'] >= 4096
        await plans.compact_plan(CITIES[0], request.model_copy(update={'style':'budget'}), sdk, 'test', 'key')
        assert fake.generate_content_async.await_count == 2
        for key, (_, value) in list(plans.CACHE.items()):
            plans.CACHE[key] = (0, value)
        await plans.compact_plan(CITIES[0], request, sdk, 'test', 'key')
        assert fake.generate_content_async.await_count == 3
    asyncio.run(run())


@pytest.mark.parametrize('raw', ['[]', 'not json', '[[[99,"산책","도보"]]]',
                               '[[["명소","산책","도보"]]]'])
def test_incomplete_or_invalid_routes_rejected(raw):
    with pytest.raises(HTTPException):
        plans.render_plan(raw, {'days':1, 'places':['경복궁']})


def test_place_ids_render_korean_without_translation():
    raw = json.dumps([[[0, '산책', '도보']] * 3])
    text = plans.render_plan(raw, {'days':1, 'places':['경복궁']})
    assert text.count('경복궁') == 3
    assert '오전:' in text and '저녁:' in text


def test_failed_generation_is_not_cached_or_automatically_retried():
    async def run():
        fake = SimpleNamespace(generate_content_async=AsyncMock(return_value=SimpleNamespace(
            candidates=[SimpleNamespace(finish_reason=2)], text='partial')))
        sdk = SimpleNamespace(GenerativeModel=lambda **kwargs: fake)
        request = ItineraryRequest(cityName=CITIES[0]['cityName'], budget=500000)
        with pytest.raises(HTTPException):
            await plans.compact_plan(CITIES[0], request, sdk, 'test', 'key')
        assert not plans.CACHE
        fake.generate_content_async.assert_awaited_once()
    asyncio.run(run())


def test_gemini3_uses_low_thinking_rest_and_reuses_success(monkeypatch):
    calls=[]
    real_client=httpx.AsyncClient
    def handler(request):
        body=json.loads(request.content)
        calls.append(body)
        assert request.headers['x-goog-api-key']=='test-secret'
        assert 'test-secret' not in str(request.url)
        assert body['generationConfig']['thinkingConfig']=={'thinkingLevel':'low'}
        assert body['generationConfig']['maxOutputTokens']>=4096
        return httpx.Response(200,json={'candidates':[{'finishReason':'STOP','content':{'parts':[
            {'text':'hidden reasoning','thought':True},
            {'text':quality_response(3)},
        ]}}]})
    monkeypatch.setattr(plans.httpx,'AsyncClient',lambda **kw:real_client(transport=httpx.MockTransport(handler)))
    monkeypatch.setenv('GEMINI_ITINERARY_THINKING_LEVEL','low')
    async def run():
        request=ItineraryRequest(cityName=CITIES[0]['cityName'],budget=500000)
        # SDK has no methods: this model must use the REST transport.
        result=await plans.compact_plan(CITIES[0],request,object(),'gemini-3.8-flash','test-secret')
        assert '3일차' in result and 'hidden reasoning' not in result
        assert await plans.compact_plan(CITIES[0],request,object(),'gemini-3.8-flash','test-secret')==result
    asyncio.run(run())
    assert len(calls)==1


@pytest.mark.parametrize('status,expected',[(429,429),(403,502),(404,502),(500,502)])
def test_gemini3_errors_are_safe_and_not_cached(monkeypatch,status,expected):
    real_client=httpx.AsyncClient
    def handler(request):
        return httpx.Response(status,json={'error':'private provider details'})
    monkeypatch.setattr(plans.httpx,'AsyncClient',lambda **kw:real_client(transport=httpx.MockTransport(handler)))
    async def run():
        request=ItineraryRequest(cityName=CITIES[0]['cityName'],budget=500000)
        with pytest.raises(HTTPException) as error:
            await plans.compact_plan(CITIES[0],request,object(),'gemini-3.8-flash','test-secret')
        assert error.value.status_code==expected
        assert 'private' not in error.value.detail and 'test-secret' not in error.value.detail
        assert not plans.CACHE
    asyncio.run(run())


def test_thinking_level_defaults_and_model_compatibility(monkeypatch):
    monkeypatch.delenv('GEMINI_ITINERARY_THINKING_LEVEL',raising=False)
    assert plans.thinking_level('gemini-3.8-flash')=='low'
    assert plans.thinking_level('gemini-3.1-flash-lite')=='minimal'
    assert plans.thinking_level('gemini-2.5-flash') is None
    monkeypatch.setenv('GEMINI_ITINERARY_THINKING_LEVEL','minimal')
    assert plans.thinking_level('gemini-3.8-flash')=='low'
    monkeypatch.setenv('GEMINI_ITINERARY_THINKING_LEVEL','high')
    assert plans.thinking_level('models/gemini-3.8-flash')=='high'


def test_explicit_regeneration_refreshes_cache_once():
    async def run():
        fake=SimpleNamespace(generate_content_async=AsyncMock(return_value=SimpleNamespace(
            candidates=[SimpleNamespace(finish_reason=1)],text=quality_response(3))))
        sdk=SimpleNamespace(GenerativeModel=lambda **kwargs:fake)
        request=ItineraryRequest(cityName=CITIES[0]['cityName'],budget=500000)
        await plans.compact_plan(CITIES[0],request,sdk,'test','key')
        await plans.compact_plan(CITIES[0],request,sdk,'test','key')
        assert fake.generate_content_async.await_count==1
        await plans.compact_plan(CITIES[0],request.model_copy(update={'refresh':True}),sdk,'test','key')
        assert fake.generate_content_async.await_count==2
    asyncio.run(run())


def test_overload_retries_with_backoff_then_returns_success():
    unavailable = plans.provider_failure(httpx.Response(503, json={}))
    generate = AsyncMock(side_effect=[unavailable, unavailable, 'verified plan'])
    sleep = AsyncMock()
    with patch.object(plans, '_generate_fast', generate), patch.object(plans.asyncio, 'sleep', sleep):
        result = asyncio.run(plans._generate_with_retry('{}', 'instruction', 'model', 'secret', None, 3))
    assert result == 'verified plan'
    assert generate.await_count == 3
    assert [call.args[0] for call in sleep.await_args_list] == [1, 2]


def test_persistent_overload_stops_after_three_attempts():
    generate = AsyncMock(side_effect=plans.provider_failure(httpx.Response(503, json={})))
    with patch.object(plans, '_generate_fast', generate), patch.object(plans.asyncio, 'sleep', AsyncMock()):
        with pytest.raises(HTTPException) as error:
            asyncio.run(plans._generate_with_retry('{}', 'instruction', 'model', 'secret', None, 3))
    assert error.value.status_code == 503
    assert generate.await_count == 3


@pytest.mark.parametrize('error', [
    plans.provider_failure(httpx.Response(429, json={})),
    plans.provider_failure(httpx.Response(403, json={})),
    HTTPException(504, 'timeout'),
    HTTPException(502, 'invalid response'),
])
def test_other_failures_do_not_retry_generation(error):
    generate = AsyncMock(side_effect=error)
    with patch.object(plans, '_generate_fast', generate), patch.object(plans.asyncio, 'sleep', AsyncMock()) as sleep:
        with pytest.raises(HTTPException):
            asyncio.run(plans._generate_with_retry('{}', 'instruction', 'model', 'secret', None, 3))
    generate.assert_awaited_once()
    sleep.assert_not_awaited()
