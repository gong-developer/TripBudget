import asyncio
import json
from unittest.mock import AsyncMock,patch
import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.gemini_keys import configured_keys,with_key_failover,provider_failure,COOLDOWNS
from app import compact_itinerary as plans
from app.main import app,CITIES,ItineraryRequest
from plan_fixtures import quality_response


def quota(daily=False):
    return provider_failure(httpx.Response(429,headers={'Retry-After':'120'},json={'error':{'details':[{
        'violations':[{'quotaId':'RequestsPerDayPerProject' if daily else 'RequestsPerMinutePerProject'}]}]}}))


def test_key_configuration_prioritizes_list_and_deduplicates(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY','single')
    monkeypatch.setenv('GEMINI_API_KEYS',' first, second, first\n third ')
    assert configured_keys()==('first','second','third')
    monkeypatch.setenv('GEMINI_API_KEYS','')
    assert configured_keys()==('single',)


def test_quota_failover_remembers_working_key_and_skips_exhausted_key():
    calls=[]
    async def generate(key):
        calls.append(key)
        if key=='first':raise quota()
        return 'itinerary'
    async def run():
        assert await with_key_failover(('first','backup'),'model',generate)=='itinerary'
        assert await with_key_failover(('first','backup'),'model',generate)=='itinerary'
    asyncio.run(run())
    assert calls==['first','backup','backup']


def test_all_exhausted_keys_fail_without_repeating_and_include_retry_after():
    generate=AsyncMock(side_effect=quota())
    async def run():
        for _ in range(2):
            with pytest.raises(HTTPException) as error:
                await with_key_failover(('first','backup'),'model',generate)
            assert error.value.status_code==429
            assert int(error.value.headers['Retry-After'])>0
            assert 'first' not in error.value.detail and 'backup' not in error.value.detail
    asyncio.run(run())
    assert generate.await_count==2


@pytest.mark.parametrize('status',[400,401,403,404,500,503])
def test_non_quota_errors_do_not_cycle_keys(status):
    generate=AsyncMock(side_effect=provider_failure(httpx.Response(status,json={'error':{'message':'secret key first'}})))
    with pytest.raises(HTTPException) as error:
        asyncio.run(with_key_failover(('first','backup'),'model',generate))
    generate.assert_awaited_once_with('first')
    assert 'secret' not in error.value.detail


def test_cooldown_expires_and_daily_quota_resets_at_next_pacific_midnight():
    error=quota(daily=True)
    assert error.kind=='daily_quota' and error.retry_after>=120
    assert provider_failure(httpx.Response(429,headers={'Retry-After':'1'},json={})).retry_after==1
    async def run():
        failing=AsyncMock(side_effect=quota())
        with pytest.raises(HTTPException):await with_key_failover(('first',),'model',failing)
        for identity in list(COOLDOWNS):COOLDOWNS[identity]=(0,'rate_limit')
        assert await with_key_failover(('first',),'model',AsyncMock(return_value='ok'))=='ok'
    asyncio.run(run())


def test_failover_coalesces_concurrent_itineraries_and_grounds_places_once():
    async def run():
        requests=[]
        async def generate(payload,instruction,model,key,level,days):
            requests.append(key)
            if key=='first':raise quota()
            return quality_response(days)
        plans.CACHE.clear();plans.INFLIGHT.clear()
        request=ItineraryRequest(cityName=CITIES[0]['cityName'],budget=1000000)
        with patch('app.compact_itinerary._generate_fast',side_effect=generate), \
             patch('app.compact_itinerary.prepare_itinerary',wraps=plans.prepare_itinerary) as prepare:
            a,b=await asyncio.gather(*[plans.compact_plan(CITIES[0],request,None,'gemini-3.1-flash-lite',('first','backup')) for _ in range(2)])
            assert a==b
            assert await plans.compact_plan(CITIES[0],request,None,'gemini-3.1-flash-lite',('first','backup'))==a
        assert requests==['first','backup']
        assert prepare.call_count==1
    asyncio.run(run())


def test_api_accepts_key_pool_without_single_key_and_exposes_no_credentials(monkeypatch):
    monkeypatch.delenv('GEMINI_API_KEY',raising=False)
    monkeypatch.setenv('GEMINI_API_KEYS','first,backup')
    monkeypatch.setenv('DEMO_MODE','false')
    client=TestClient(app)
    assert client.get('/api/health').json()['aiConfigured'] is True
    plans.CACHE.clear();plans.INFLIGHT.clear()
    with patch('app.compact_itinerary._generate_fast',new=AsyncMock(return_value=quality_response(1))) as generate:
        result=client.post('/api/generate-itinerary',json={'cityName':CITIES[0]['cityName'],'budget':1000000,'days':1})
    assert result.status_code==200
    assert generate.call_args.args[3]=='first'
    assert 'first' not in result.text and 'backup' not in result.text


def test_generated_place_ids_and_explicit_required_highlights_are_supplied(monkeypatch):
    async def prepare(data):
        return {**data,'places':[{'name':f'명소 {i}','originalName':f'명소 {i}','lat':35,'lng':129,
                                 'priority':i==0} for i in range(3)]}
    def generate(payload,*args):
        data=json.loads(payload)
        assert [p['id'] for p in data['places']]==[0,1,2]
        assert data['requiredHighlights']=={'placeIds':[0],'minimum':1}
        return quality_response(1)
    plans.CACHE.clear();plans.INFLIGHT.clear()
    with patch('app.compact_itinerary.prepare_itinerary',side_effect=prepare),patch('app.compact_itinerary._generate_fast',new=AsyncMock(side_effect=generate)):
        asyncio.run(plans.compact_plan(CITIES[0],ItineraryRequest(cityName=CITIES[0]['cityName'],budget=1000000,days=1),None,'gemini-3.1-flash-lite','key'))
