import asyncio
from unittest.mock import patch
import httpx
import pytest
from fastapi import HTTPException
from app.budget_recommendation import choose_budget_destination, choose_budget_destinations
from app.costs import TripOptions
from app.destinations import budget_candidates


def city(name, high, category='domestic'):
    return {'cityName':name, 'category':category, 'high':high}


def priced(candidate, options):
    return {**candidate, 'costBreakdown':{'high':candidate['high']}}


def test_closest_candidates_only_and_never_over_budget():
    candidates=[city('저렴한 곳',40),city('가까운 곳',90),city('최적',95),city('초과',101)]
    with patch('app.budget_recommendation.priced_city',side_effect=priced), \
         patch('app.budget_recommendation.random.choice',side_effect=lambda rows:rows[0]) as choose:
        result,_=choose_budget_destination(candidates,TripOptions(),100,'all')
    pool=choose.call_args.args[0]
    assert {c['cityName'] for c,_ in pool}=={'가까운 곳','최적'}
    assert result['cityName']=='가까운 곳'


def test_category_filter_dedup_and_exact_budget():
    candidates=[city('같은 곳',100),city('같은 곳',100),city('해외',100,'international')]
    with patch('app.budget_recommendation.priced_city',side_effect=priced), \
         patch('app.budget_recommendation.random.choice',side_effect=lambda rows:rows[-1]) as choose:
        result,_=choose_budget_destination(candidates,TripOptions(),100,'domestic')
    assert result['cityName']=='같은 곳'
    assert len(choose.call_args.args[0])==1


def test_best_available_when_all_candidates_well_below_budget():
    with patch('app.budget_recommendation.priced_city',side_effect=priced):
        result,_=choose_budget_destination([city('최선',40),city('낮음',30)],TripOptions(),100,'all')
    assert result['cityName']=='최선'


def test_empty_or_over_budget_pool_fails():
    with patch('app.budget_recommendation.priced_city',side_effect=priced):
        for candidates in ([],[city('초과',101)]):
            with pytest.raises(HTTPException) as error:
                choose_budget_destination(candidates,TripOptions(),100,'all')
            assert error.value.status_code==404


def test_comparison_includes_all_affordable_candidates_sorted_by_cost():
    candidates = [city('정확히 예산',100), city('저렴',10), city('중간',50),
                  city('다른 후보',75), city('추가 후보',80), city('초과',101),
                  city('저렴',10), city('해외',20,'international')]
    with patch('app.budget_recommendation.priced_city',side_effect=priced) as price:
        result = choose_budget_destinations(candidates,TripOptions(),100,'domestic')
    assert [candidate['cityName'] for candidate,_ in result] == ['저렴','중간','다른 후보','추가 후보','정확히 예산']
    assert price.call_count == 6


def test_comparison_rejects_empty_or_unaffordable_candidates():
    with patch('app.budget_recommendation.priced_city',side_effect=priced):
        for candidates in ([],[city('초과',101)]):
            with pytest.raises(HTTPException) as error:
                choose_budget_destinations(candidates,TripOptions(),100,'all')
            assert error.value.status_code == 404


def test_domestic_budget_compares_regions_without_querying_sights(monkeypatch):
    monkeypatch.delenv('TOUR_API_KEY', raising=False)
    with patch('httpx.AsyncClient',side_effect=AssertionError('Region comparison needs no sight API')):
        candidates=asyncio.run(budget_candidates('domestic'))
    assert len(candidates)==162
    assert len({city['regionId'] for city in candidates})==162
    assert all(city['destinationType']=='region' and city['recommendedPlaces']==[] for city in candidates)
    assert any(city['originalName']=='강릉시' for city in candidates)


def test_international_uses_geoapify_candidates():
    from unittest.mock import AsyncMock
    rows=[{'cityName':'도시','category':'international'}, {'cityName':'다른 도시','category':'international'}]
    with patch('app.destinations.overseas_candidates',new=AsyncMock(return_value=rows)) as provider:
        candidates=asyncio.run(budget_candidates('international'))
    assert candidates==rows
    provider.assert_awaited_once_with()
