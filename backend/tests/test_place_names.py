import asyncio
import httpx
import pytest
from app.place_names import korean_names,korean_only,localize_destination_label,NAME_POLICY


def run(row):
    return asyncio.run(korean_names(None,row))


def test_registered_persian_and_country_names_need_no_translation():
    assert run({'city':'تهران','country_code':'ir','lat':35,'lon':51})==('테헤란','이란',True)


def test_unknown_native_name_preserves_original_even_with_gemini_key(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY','test-key')
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:pytest.fail('No translation API'))
    assert run({'city':'اردکان','country_code':'ir'})==('اردکان','이란',False)


def test_existing_provider_korean_is_preserved():
    assert run({'city':'야즈드','country_code':'ir'})==('야즈드','이란',True)


@pytest.mark.parametrize('name',['전체메뉴','스낵 바','숙박 약관','채용정보'])
def test_obviously_invalid_place_labels_are_not_validated_by_hangul_alone(name):
    assert not korean_only(name)


def test_original_identity_recovers_registered_name_from_old_placeholder():
    city={'cityName':'도시명 번역 미확인 (29.600, 52.500) · 이란','originalName':'شیراز',
          'lat':29.6,'lng':52.5,'countryCode':'ir','category':'international'}
    result=asyncio.run(localize_destination_label(city))
    assert result['displayName']=='시라즈 · 이란' and result['cityName']==city['cityName']


def test_old_machine_display_name_is_discarded():
    city={'cityName':'Exampletown · Iceland','originalName':'Exampletown','displayName':'스낵 바 · 아이슬란드',
          'nameLocalized':True,'lat':64.14,'lng':-21.94,'countryCode':'is','category':'international'}
    result=asyncio.run(localize_destination_label(city,allow_original=True))
    assert result['displayName']=='Exampletown · 아이슬란드'
    assert result['nameLocalized'] is False and result['namePolicy']==NAME_POLICY


def test_registered_english_alias_can_resolve_native_name_without_api():
    assert run({'city':'未知都市','country_code':'jp','name_international':{'en':'Tokyo'}})==('도쿄','일본',True)
    assert run({'city':'未知都市','country_code':'jp','name_international':{'en':'Unknown City'}})==('未知都市','일본',False)


def test_display_name_endpoint_returns_provenance():
    from fastapi.testclient import TestClient
    from app.main import app
    response=TestClient(app).post('/api/destinations/display-name',json={
        'cityName':'Tehran · Iran','lat':35.69,'lng':51.39,'countryCode':'ir','category':'international'})
    assert response.status_code==200
    assert response.json()['displayName']=='테헤란 · 이란'
    assert response.json()['namePolicy']==NAME_POLICY
