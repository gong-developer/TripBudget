import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from app.main import app, CITIES, ItineraryRequest
from app.costs import TripOptions, estimate
from app import compact_itinerary as plans
from app.travel_themes import THEMES
from plan_fixtures import quality_response


@pytest.mark.parametrize('theme',list(THEMES))
def test_legacy_theme_reaches_ai_payload_instruction_and_costs(monkeypatch,theme):
    monkeypatch.setenv('GEMINI_API_KEY','theme-test-key')
    monkeypatch.setenv('GEMINI_ITINERARY_MODEL','theme-test-model')
    monkeypatch.setenv('DEMO_MODE','false')
    plans.CACHE.clear();plans.INFLIGHT.clear()
    client=TestClient(app)
    with patch.object(plans,'_generate_fast',AsyncMock(return_value=quality_response(3))) as generate:
        result=client.post('/api/generate-itinerary',json={'cityName':CITIES[0]['cityName'],'budget':1000000,'theme':theme})
    assert result.status_code==200
    payload,instruction=generate.call_args.args[:2]
    assert json.loads(payload)['theme']==theme
    assert f'여행 카테고리는 {THEMES[theme][0]}' in instruction
    themed=estimate(CITIES[0],TripOptions(theme=theme))
    assert themed['total']>=estimate(CITIES[0],TripOptions())['total']
    assert themed['themeBudget']['themes']==[THEMES[theme][0]]


def test_different_themes_do_not_reuse_same_itinerary_cache():
    plans.CACHE.clear();plans.INFLIGHT.clear()
    async def run():
        generate=AsyncMock(return_value=quality_response(3))
        request=ItineraryRequest(cityName=CITIES[0]['cityName'],budget=1000000,theme='food')
        with patch.object(plans,'_generate_fast',generate):
            first=await plans.compact_plan(CITIES[0],request,None,'theme-cache-test','key')
            assert await plans.compact_plan(CITIES[0],request,None,'theme-cache-test','key')==first
            await plans.compact_plan(CITIES[0],request.model_copy(update={'theme':'photography'}),None,'theme-cache-test','key')
        assert generate.await_count==2
    asyncio.run(run())


def test_random_accepts_theme_and_invalid_category_is_rejected_before_provider():
    client=TestClient(app)
    with patch('app.main.random_destination',AsyncMock(return_value=CITIES[0])) as provider:
        assert client.get('/api/destinations/random',params={'theme':'nature'}).status_code==200
        assert client.get('/api/destinations/random',params={'theme':'not-a-theme'}).status_code==422
        assert client.post('/api/destinations/compare',json={'budget':1000000,'theme':'not-a-theme'}).status_code==422
        provider.assert_awaited_once()


def test_multi_selection_costs_scale_by_days_and_people_with_correct_buffer():
    base=estimate(CITIES[0],TripOptions(days=3,people=2,themes=[]))
    themed=estimate(CITIES[0],TripOptions(days=3,people=2,themes=['food','shopping','activity']))
    rows={item['key']:item for item in themed['items']}
    assert rows['shopping']['amount']==30000*3*2
    assert rows['activities']['amount']==25000*3*2
    assert rows['food']['amount']==42900*3*2
    extra=30000*3*2+25000*3*2+9900*3*2
    assert themed['themeBudget']['additional']==extra
    assert themed['total']-base['total']==extra+round(extra*.1)
    assert themed['high']>=themed['total']>=themed['low']
    assert sum(row['amount'] for row in themed['items'])==themed['total']


def test_duplicates_and_selection_order_never_double_charge():
    first=TripOptions(themes=['shopping','food','shopping'])
    second=TripOptions(themes=['food','shopping'])
    assert first.selected_themes==second.selected_themes
    assert estimate(CITIES[0],first)==estimate(CITIES[0],second)


def test_overlapping_relaxation_and_photography_allowances_are_not_added_twice():
    photo=estimate(CITIES[0],TripOptions(themes=['photography']))
    both=estimate(CITIES[0],TripOptions(themes=['relaxation','photography']))
    assert photo['themeBudget']['additional']==both['themeBudget']['additional']
    assert sum(item['key']=='leisure' for item in both['items'])==1


def test_trekking_is_per_trip_and_manual_transport_and_hotel_are_preserved():
    options=dict(people=3,transportPerPerson=10000,hotelPerRoomNight=22222)
    base=estimate(CITIES[0],TripOptions(**options,themes=[]))
    themed=estimate(CITIES[0],TripOptions(**options,themes=['food','shopping','nature']))
    base_rows={row['key']:row for row in base['items']}
    rows={row['key']:row for row in themed['items']}
    for key in ('transport','lodging'):
        assert rows[key]==base_rows[key]
        assert rows[key]['low']==rows[key]['high']==rows[key]['amount']
    assert rows['trekking']['amount']==15000*3
    longer=estimate(CITIES[0],TripOptions(**options,themes=['nature'],days=7))
    assert next(row for row in longer['items'] if row['key']=='trekking')['amount']==15000*3


def test_theme_allowance_changes_affordability_without_exceeding_user_budget():
    from app.budget_recommendation import choose_budget_destinations
    from fastapi import HTTPException
    base=TripOptions(themes=[])
    budget=estimate(CITIES[0],base)['high']
    assert choose_budget_destinations([CITIES[0]],base,budget,'domestic')
    with pytest.raises(HTTPException) as error:
        choose_budget_destinations([CITIES[0]],TripOptions(themes=['shopping']),budget,'domestic')
    assert error.value.status_code==404


def test_multiple_ai_themes_share_cache_independent_of_click_order():
    plans.CACHE.clear();plans.INFLIGHT.clear()
    async def run():
        generate=AsyncMock(return_value=quality_response(3))
        requests=[ItineraryRequest(cityName=CITIES[0]['cityName'],budget=1000000,themes=themes)
                  for themes in (['shopping','food'],['food','shopping'])]
        with patch.object(plans,'_generate_fast',generate):
            for request in requests:
                await plans.compact_plan(CITIES[0],request,None,'multi-theme-cache','key')
        generate.assert_awaited_once()
        payload,instruction=generate.call_args.args[:2]
        assert json.loads(payload)['themes']==['food','shopping']
        assert '맛집 · 쇼핑' in instruction
    asyncio.run(run())


def test_random_query_supports_repeated_and_empty_themes():
    client=TestClient(app)
    with patch('app.main.random_destination',AsyncMock(return_value=CITIES[0])):
        result=client.get('/api/destinations/random?themes=food&themes=shopping').json()['city']
        assert 'shopping' in {row['key'] for row in result['costBreakdown']['items']}
        assert result['costBreakdown']['themeBudget']['themes']==['맛집','쇼핑']
        empty=client.get('/api/destinations/random?themes=').json()['city']
        assert empty['costBreakdown']['themeBudget']['themes']==[]
        assert client.get('/api/destinations/random?themes=unknown').status_code==422


def test_multi_theme_validation_rejects_invalid_names_and_limits_list_length():
    from pydantic import ValidationError
    for themes in (['unknown'],['shopping']*8,'shopping'):
        with pytest.raises(ValidationError):TripOptions(themes=themes)
    assert TripOptions(theme='food',themes=[]).selected_themes==[]
