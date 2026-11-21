import itertools
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import pytest
from google.api_core import exceptions as google_errors
from fastapi.testclient import TestClient
from app.main import app, CITIES
from app.optimizer import recommend
from plan_fixtures import quality_response

client = TestClient(app)

@pytest.fixture(autouse=True)
def clear_itinerary_cache(monkeypatch):
    monkeypatch.delenv('GEMINI_ITINERARY_MODEL', raising=False)
    # Explicit model selection; production uses a request-scoped REST API key.
    monkeypatch.setenv('GEMINI_MODEL', 'gemini-1.5-flash-latest')
    from app.compact_itinerary import CACHE, INFLIGHT
    CACHE.clear()
    INFLIGHT.clear()

def compact_response(days):
    return quality_response(days)

@pytest.mark.parametrize("budget", [1, 349999, 350000, 849999, 1500000, 3000000, 100000000])
def test_knapsack_matches_exhaustive_optimum(budget):
    choices = [combo for n in range(4) for combo in itertools.combinations(CITIES, n)
               if sum(c["estimatedCost"] for c in combo) <= budget]
    rank = lambda combo: (len(combo), sum(c["satisfaction"] for c in combo), -sum(c["estimatedCost"] for c in combo))
    actual = recommend(CITIES, budget)
    assert rank(actual) == max(map(rank, choices))
    assert len({c["cityName"] for c in actual}) == len(actual)

def test_api_recommend():
    response = client.post("/api/recommend", json={"budget": 1500000})
    assert response.status_code == 200
    result = response.json()
    from app.costs import priced_city, TripOptions
    expected = recommend([priced_city(city,TripOptions()) for city in CITIES],1500000)
    assert [{key:value for key,value in city.items() if key not in ('sightCount','sightsVerified')} for city in result["cities"]] == expected
    assert all(city['sightsVerified'] and city['sightCount']>0 for city in result["cities"])
    assert result["totalCost"] <= 1500000

@pytest.mark.parametrize("category", ["domestic", "international"])
def test_category_filters_cities_and_recommendations(category):
    expected = [city for city in CITIES if city["category"] == category]
    response = client.get("/api/cities", params={"category":category})
    assert response.status_code == 200
    assert response.json() == expected
    response = client.post("/api/recommend", json={"budget":100000000, "category":category})
    assert response.status_code == 200
    selected = response.json()["cities"]
    assert len(selected) == min(3, len(expected))
    assert all(city["category"] == category for city in selected)

def test_category_validation_and_default():
    assert client.get("/api/cities").json() == CITIES
    assert client.get("/api/cities?category=invalid").status_code == 422
    assert client.post("/api/recommend", json={"budget":500000, "category":"invalid"}).status_code == 422

def test_category_with_no_affordable_city():
    response = client.post("/api/recommend", json={"budget":1, "category":"international"})
    assert response.status_code == 200
    assert response.json()["cities"] == []

@pytest.mark.parametrize("value", [0, -1, 1.5, "1000", True, 100000001])
def test_invalid_budget(value):
    assert client.post("/api/recommend", json={"budget": value}).status_code == 422

def test_cors():
    response = client.options("/api/recommend", headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"

def test_missing_key_is_not_fake_ai(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert client.post("/api/generate-itinerary", json={"cityName": CITIES[0]["cityName"], "budget": 500000}).status_code == 503

def test_demo_explicitly_labeled(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    response = client.post("/api/generate-itinerary", json={"cityName": CITIES[0]["cityName"], "budget": 500000})
    assert response.status_code == 200
    assert response.json()["source"] == "demo"

def test_unknown_city():
    assert client.post("/api/generate-itinerary", json={"cityName":"unknown", "budget":500000}).status_code == 404

@pytest.mark.parametrize("days", [1, 7, 14])
def test_demo_selected_duration(monkeypatch, days):
    monkeypatch.setenv("DEMO_MODE", "true")
    response = client.post("/api/generate-itinerary", json={"cityName":CITIES[0]["cityName"], "budget":500000, "days":days})
    assert response.status_code == 200
    text = response.json()["text"]
    assert text.count("DAY ") == days
    assert f"DAY {days} ·" in text

@pytest.mark.parametrize("days", [0, 15, -1, 1.5, True, "7"])
def test_invalid_duration(days):
    assert client.post("/api/generate-itinerary", json={"cityName":CITIES[0]["cityName"], "budget":500000, "days":days}).status_code == 422

def test_ai_receives_selected_duration(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("GEMINI_API_KEY", "test-placeholder")
    with patch('app.compact_itinerary._generate_fast',new=AsyncMock(return_value=compact_response(14))) as generate:
        response = client.post('/api/generate-itinerary',json={'cityName':CITIES[0]['cityName'],'budget':500000,'days':14})
    assert response.status_code==200
    assert '14일차' in generate.call_args.args[1]
    assert json.loads(generate.call_args.args[0])['days']==14


def test_itinerary_model_override_uses_fast_model_without_changing_general_model(monkeypatch):
    monkeypatch.setenv('DEMO_MODE','false')
    monkeypatch.setenv('GEMINI_API_KEY','test-placeholder')
    monkeypatch.setenv('GEMINI_MODEL','gemini-3.8-flash')
    monkeypatch.setenv('GEMINI_ITINERARY_MODEL','gemini-3.1-flash-lite')
    monkeypatch.setenv('GEMINI_ITINERARY_THINKING_LEVEL','minimal')
    with patch('app.compact_itinerary._generate_fast',new=AsyncMock(return_value=compact_response(3))) as generate:
        response=client.post('/api/generate-itinerary',json={'cityName':CITIES[0]['cityName'],'budget':1000000})
    assert response.status_code==200 and response.json()['source']=='gemini'
    assert generate.call_args.args[2]=='gemini-3.1-flash-lite'
    assert generate.call_args.args[4]=='minimal'

@pytest.mark.parametrize("configured,expected", [
    (None, "gemini-3.1-flash-lite"),
    ("", "gemini-3.1-flash-lite"),
    ("gemini-1.5-flash-latest", "gemini-1.5-flash-latest"),
    (" gemini-1.5-pro ", "gemini-1.5-pro"),
])
def test_llm_response_contract(monkeypatch, configured, expected):
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("GEMINI_API_KEY", "test-placeholder")
    if configured is None:
        monkeypatch.delenv("GEMINI_MODEL", raising=False)
    else:
        monkeypatch.setenv("GEMINI_MODEL", configured)
    with patch('app.compact_itinerary._generate_fast',new=AsyncMock(return_value=compact_response(3))) as fast:
        response=client.post('/api/generate-itinerary',json={'cityName':CITIES[0]['cityName'],'budget':500000})
    assert response.status_code==200
    assert set(response.json())=={'text','source','cityName'}
    assert response.json()['source']=='gemini' and '3일차' in response.json()['text']
    assert fast.call_args.args[2]==expected
    assert fast.call_args.args[3]=='test-placeholder'


@pytest.mark.parametrize("error,status", [
    (google_errors.NotFound("retired"), 502),
    (google_errors.ResourceExhausted("quota"), 429),
    (google_errors.DeadlineExceeded("timeout"), 504),
    (TimeoutError(), 504),
    (google_errors.PermissionDenied("denied"), 502),
    (google_errors.InvalidArgument("bad key"), 502),
])
def test_gemini_errors(monkeypatch, error, status):
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("GEMINI_API_KEY", "test-placeholder")
    with patch("app.compact_itinerary._generate_fast", new=AsyncMock(side_effect=error)):
        response = client.post("/api/generate-itinerary", json={"cityName":CITIES[0]["cityName"],"budget":500000})
    assert response.status_code == status
    assert isinstance(response.json()["detail"], str)
    assert "test-placeholder" not in response.text

@pytest.mark.parametrize('result', [{}, {'candidates':[]}, {'candidates':[{'finishReason':'MAX_TOKENS'}]}])
def test_empty_blocked_or_truncated_response(monkeypatch,result):
    import httpx
    monkeypatch.setenv('DEMO_MODE','false')
    monkeypatch.setenv('GEMINI_API_KEY','test-placeholder')
    real_client=httpx.AsyncClient
    with patch('app.compact_itinerary.httpx.AsyncClient',side_effect=lambda **kw:real_client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json=result)))):
        response=client.post('/api/generate-itinerary',json={'cityName':CITIES[0]['cityName'],'budget':500000})
    assert response.status_code==502


def test_health_uses_gemini_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "unused-test-key")
    assert client.get("/api/health").json()["aiConfigured"] is False
    monkeypatch.setenv("GEMINI_API_KEY", "test-placeholder")
    assert client.get("/api/health").json()["aiConfigured"] is True
