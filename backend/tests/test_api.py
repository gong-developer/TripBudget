import itertools
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import pytest
from google.api_core import exceptions as google_errors
from fastapi.testclient import TestClient
from app.main import app, CITIES
from app.optimizer import recommend

client = TestClient(app)

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
    assert len(result["cities"]) == 3
    assert result["totalCost"] <= 1500000

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

@pytest.mark.parametrize("configured,expected", [
    (None, "gemini-1.5-flash-latest"),
    ("", "gemini-1.5-flash-latest"),
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
    fake = SimpleNamespace(generate_content_async=AsyncMock(return_value=SimpleNamespace(
        candidates=[SimpleNamespace(finish_reason=1)], text="DAY 1\n여행\nDAY 2\n휴식\nDAY 3\n귀가")))
    with patch("app.main.genai.configure") as configure, patch("app.main.genai.GenerativeModel", return_value=fake) as model:
        response = client.post("/api/generate-itinerary", json={"cityName":CITIES[0]["cityName"],"budget":500000})
    assert response.status_code == 200
    assert set(response.json()) == {"text", "source", "cityName"}
    assert response.json()["source"] == "gemini"
    assert "DAY 3" in response.json()["text"]
    configure.assert_called_once_with(api_key="test-placeholder")
    assert model.call_args.kwargs["model_name"] == expected
    fake.generate_content_async.assert_awaited_once()

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
    fake = SimpleNamespace(generate_content_async=AsyncMock(side_effect=error))
    with patch("app.main.genai.configure"), patch("app.main.genai.GenerativeModel", return_value=fake):
        response = client.post("/api/generate-itinerary", json={"cityName":CITIES[0]["cityName"],"budget":500000})
    assert response.status_code == status
    assert isinstance(response.json()["detail"], str)
    assert "test-placeholder" not in response.text

@pytest.mark.parametrize("candidates,text", [
    ([], ""), ([SimpleNamespace(finish_reason=2)], "partial"),
    ([SimpleNamespace(finish_reason=3)], ""), ([SimpleNamespace(finish_reason=1)], " "),
])
def test_empty_blocked_or_truncated_response(monkeypatch, candidates, text):
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("GEMINI_API_KEY", "test-placeholder")
    fake = SimpleNamespace(generate_content_async=AsyncMock(return_value=SimpleNamespace(candidates=candidates, text=text)))
    with patch("app.main.genai.configure"), patch("app.main.genai.GenerativeModel", return_value=fake):
        response = client.post("/api/generate-itinerary", json={"cityName":CITIES[0]["cityName"],"budget":500000})
    assert response.status_code == 502

def test_health_uses_gemini_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "unused-test-key")
    assert client.get("/api/health").json()["aiConfigured"] is False
    monkeypatch.setenv("GEMINI_API_KEY", "test-placeholder")
    assert client.get("/api/health").json()["aiConfigured"] is True
