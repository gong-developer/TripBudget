import asyncio
import json
from unittest.mock import AsyncMock,patch
import pytest
from fastapi import HTTPException
from app.itinerary_context import prepare_itinerary
from app.quality_itinerary import render_quality_plan, korean_text
from plan_fixtures import grounded_context, quality_response


def context(days=2):
    return asyncio.run(grounded_context({'days':days}))


def test_verified_foreign_place_names_and_identifiers_do_not_reject_korean_explanations():
    names=['動輪の広場(C62形蒸気機関車)','Central Park']
    assert korean_text('C62 기관차의 외관을 살펴보며 주변 공간을 천천히 둘러보세요.',12,180,names)
    assert korean_text('Central Park에서 주변 풍경을 보며 여유롭게 산책하세요.',12,180,names)
    with pytest.raises(ValueError):korean_text('C62 기관차의 외관을 살펴보며 주변 공간을 천천히 둘러보세요.',12,180)
    with pytest.raises(ValueError):korean_text('Central Park enjoy a beautiful walk around.',12,180,names)
    with pytest.raises(ValueError):korean_text('動輪の広場(C62形蒸気機関車)',12,180,names)


def test_rich_plan_contains_reasons_stays_meals_and_cautious_distance():
    result=render_quality_plan(quality_response(2),context())
    assert '권장 체류 90분' in result and '추천 이유:' in result and '방문 팁:' in result
    assert '식사: 점심' in result and '휴식:' in result
    assert '직선 약' in result and '실제 교통편·소요 시간 확인' in result
    assert '검증 명소 0' in result and '검증 명소 3' in result


@pytest.mark.parametrize('defect',['duplicate','unknown','overlap','far','generic','missing_meal','no_lunch','no_transfer'])
def test_low_quality_or_unrealistic_output_is_rejected(defect):
    data=context();raw=json.loads(quality_response(2))
    if defect=='duplicate':raw['days'][1]['visits'][0]['place']=0
    if defect=='unknown':raw['days'][0]['visits'][0]['place']='가짜 장소'
    if defect=='overlap':raw['days'][0]['visits'][1]['start']='10:00'
    if defect=='far':data['places'][1]['lat']=50
    if defect=='generic':raw['days'][0]['visits'][1]['activity']=raw['days'][0]['visits'][0]['activity']
    if defect=='missing_meal':raw['days'][0]['lunch']=''
    if defect=='no_lunch':
        raw['days'][0]['visits'][0].update(start='11:00',minutes=180)
        raw['days'][0]['visits'][1]['start']='14:30'
    if defect=='no_transfer':
        data['places'][0]['lat']=None
        raw['days'][0]['visits'][1]['start']='11:10'
    with pytest.raises(HTTPException) as error:
        render_quality_plan(json.dumps(raw),data)
    assert error.value.status_code==502


def test_place_context_uses_provider_coordinates_and_rejects_distant_duplicates():
    features=[{'properties':{'name':f'확인 명소 {i}','lat':35+i*.001,'lon':129,'place_id':str(i)}} for i in range(6)]
    features.extend([features[0],{'properties':{'name':'멀리 있는 곳','lat':1,'lon':1}},
                     {'properties':{'name':'전체메뉴','lat':35,'lon':129}}])
    data={'city':'테스트 도시','location':[35,129],'days':2,'places':['등록 추천 명소']}
    with patch('app.itinerary_context.geo_request',new=AsyncMock(return_value={'features':features})) as request:
        result=asyncio.run(prepare_itinerary(data))
    assert len(result['places'])==7
    assert all(place['name']!='멀리 있는 곳' for place in result['places'])
    assert any(place['lat'] is not None for place in result['places'])
    assert request.await_args_list[0].args[1]['limit']==18
    assert all(place['name']!='전체메뉴' for place in result['places'])


def test_insufficient_sources_fail_instead_of_inventing_full_trip():
    data={'city':'테스트 도시','location':[35,129],'days':3,'places':['실제 등록 명소']}
    with patch('app.itinerary_context.geo_request',new=AsyncMock(side_effect=HTTPException(503,'offline'))):
        with pytest.raises(HTTPException) as error:
            asyncio.run(prepare_itinerary(data))
    assert error.value.status_code==503 and '기간을 줄이거나' in error.value.detail


def test_registered_highlights_cannot_all_be_ignored():
    data=context();data['places'][8]['priority']=True
    with pytest.raises(HTTPException):
        render_quality_plan(quality_response(2),data)


def test_curated_highlights_are_geocoded_and_prioritized():
    features=[{'properties':{'name':f'확인 명소 {i}','lat':35+i*.001,'lon':129}} for i in range(6)]
    async def provider(path,params):
        if path=='/v2/places':return {'features':features}
        return {'results':[{'name':'중요 명소','lat':35.01,'lon':129.01,'country_code':'kr',
                            'result_type':'amenity','rank':{'confidence':1}}]}
    data={'city':'테스트 도시','countryCode':'kr','location':[35,129],'days':2,'places':['중요 명소']}
    with patch('app.itinerary_context.geo_request',side_effect=provider):
        result=asyncio.run(prepare_itinerary(data))
    assert result['places'][0]['priority'] is True
    assert result['places'][0]['lat']==35.01
