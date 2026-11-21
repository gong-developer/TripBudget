import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import pytest
from fastapi import HTTPException
from app.korean_itinerary import has_foreign_words, ensure_korean

@pytest.mark.parametrize('text',['1일차 · 테헤란\n골레스탄 궁전 10,000원', 'DAY 2 · 파리\nKTX 1km, eSIM 5,000원'])
def test_korean_copy_needs_no_extra_request(text):
    assert not has_foreign_words(text)
    with patch('app.korean_itinerary.genai.GenerativeModel') as model:
        assert asyncio.run(ensure_korean(text,'test-model',3000))==text
    model.assert_not_called()

@pytest.mark.parametrize('text',['Golestan Palace','تهران','東京','วัดอรุณ','테헤란 (Tehran)'])
def test_foreign_place_names_are_detected(text):
    assert has_foreign_words(text)

def test_repair_preserves_price_and_day():
    fake=SimpleNamespace(generate_content_async=AsyncMock(return_value=SimpleNamespace(
        candidates=[SimpleNamespace(finish_reason=1)],text='1일차 · 골레스탄 궁전\n입장료 10,000원')))
    with patch('app.korean_itinerary.genai.GenerativeModel',return_value=fake):
        result=asyncio.run(ensure_korean('1일차 · Golestan Palace\n입장료 10,000원','test-model',3000))
    assert '골레스탄 궁전' in result
    assert '10,000원' in result

@pytest.mark.parametrize('translated',['1일차 · 골레스탄 궁전 20,000원','1일차 · Golestan Palace 10,000원',''])
def test_failed_or_changed_translation_is_not_shown(translated):
    fake=SimpleNamespace(generate_content_async=AsyncMock(return_value=SimpleNamespace(
        candidates=[SimpleNamespace(finish_reason=1)],text=translated)))
    with patch('app.korean_itinerary.genai.GenerativeModel',return_value=fake):
        with pytest.raises(HTTPException) as error:
            asyncio.run(ensure_korean('1일차 · Golestan Palace 10,000원','test-model',3000))
    assert error.value.status_code==502
