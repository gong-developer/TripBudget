import pytest
from app.geoapify_destinations import REGION_CACHE
from app.gemini_keys import COOLDOWNS, ACTIVE
from app.domestic_sights import CACHE as DOMESTIC_CACHE
from app.travel_services import CACHE as TRAVEL_CACHE
from plan_fixtures import grounded_context
from app import destination_sights
from unittest.mock import AsyncMock


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    monkeypatch.delenv('GEMINI_API_KEYS', raising=False)
    monkeypatch.delenv('UNSPLASH_ACCESS_KEY', raising=False)
    monkeypatch.delenv('SERPAPI_API_KEY', raising=False)
    from app import flight_quotes
    flight_quotes.CACHE.clear();flight_quotes.INFLIGHT.clear();flight_quotes.NO_RESULTS.clear()
    monkeypatch.setattr('app.unsplash_photos.UNAVAILABLE_UNTIL',0)
    COOLDOWNS.clear(); ACTIVE.clear()
    monkeypatch.setenv('DESTINATION_DB', str(tmp_path / 'destinations.sqlite3'))
    monkeypatch.setenv('API_LIMIT_DB', str(tmp_path / 'limits.sqlite3'))
    monkeypatch.setenv('MAP_TRANSLATION_CACHE', str(tmp_path / 'translations.sqlite3'))
    # Provider calls are tested separately; unit/API tests never spend real quota.
    monkeypatch.setattr('app.compact_itinerary.prepare_itinerary',grounded_context)
    destination_sights.CACHE.clear();destination_sights.INFLIGHT.clear()
    async def confirmed_place(city,days):
        return {'places':[{'name':f'검증 명소 {i}','lat':city['lat']+i*.001,'lng':city['lng']} for i in range(days*2)],'source':'test'}
    monkeypatch.setattr(destination_sights,'fetch_nearby',AsyncMock(side_effect=confirmed_place))


@pytest.fixture(autouse=True)
def clear_region_cache(isolated_storage):
    DOMESTIC_CACHE.clear()
    REGION_CACHE.clear()
    TRAVEL_CACHE.clear()
    yield
    DOMESTIC_CACHE.clear()
    REGION_CACHE.clear()
    TRAVEL_CACHE.clear()
