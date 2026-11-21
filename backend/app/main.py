import asyncio
import json
import os
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict
from dotenv import load_dotenv
from google.api_core import exceptions as google_errors
from .optimizer import recommend
from .destinations import search_destinations, random_destination, budget_candidates
from .budget_recommendation import choose_budget_destination, choose_budget_destinations
from .destination_sights import confirmed_destinations
from .costs import TripOptions, ORIGINS, priced_city, estimate
from .travel_themes import TravelTheme
from .compact_itinerary import compact_plan
from .gemini_keys import configured_keys
from .place_names import localize_destination_label
from .api_docs import configure_korean_docs
from .travel_features import install_travel_features
from .countries import filter_country, validate_country_filter
from .travel_policy import allowed_destination, require_destination
from .domestic_regions import region_history
from .map_translation import install_map_translation
from .storage import DestinationStore
from .protection import APIProtectionMiddleware
from .web import install_web

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
CITIES = json.loads((ROOT / "cities.json").read_text(encoding="utf-8"))
EXTERNAL_CITIES = DestinationStore()
app = FastAPI(title="TripBudget API", version="1.0.0")
install_map_translation(app)
configure_korean_docs(app)
origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173")
app.add_middleware(APIProtectionMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in origins.split(",") if x.strip()],
                   allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

class BudgetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    budget: int = Field(gt=0, le=100_000_000, strict=True)

class ItineraryRequest(BudgetRequest, TripOptions):
    cityName: str = Field(min_length=1, max_length=200)
    budget: int = Field(gt=0, le=1_000_000_000, strict=True)
    refresh: bool = Field(default=False, strict=True)

class RecommendRequest(BudgetRequest, TripOptions):
    category: Literal["all", "domestic", "international"] = "all"
    destinationNames: list[str] | None = Field(default=None, max_length=200)

def filter_cities(category):
    return [city for city in CITIES if allowed_destination(city) and (category == "all" or city["category"] == category)]

@app.get("/api/destinations/random")
async def destination_random(category: Literal["all", "domestic", "international"] = "all",
                             budget: int | None = Query(default=None,gt=0,le=100_000_000),
                             days: int = Query(default=3,ge=1,le=14),
                             origin: str = "seoul", people: int = Query(default=1,ge=1,le=10),
                             style: Literal['budget','standard','comfort'] = 'standard',
                             theme: TravelTheme = 'sightseeing',
                             themes: list[str] | None = Query(default=None,max_length=7),
                             departureDate: str | None = None,
                             transportPerPerson: int | None = Query(default=None,ge=0,le=20_000_000),
                             hotelPerRoomNight: int | None = Query(default=None,ge=0,le=5_000_000),
                             countryCode: str | None = Query(default=None,pattern='^[a-z]{2}$')):
    from pydantic import ValidationError
    try:
        options=TripOptions(days=days,origin=origin,people=people,style=style,theme=theme,themes=[] if themes==[''] else themes,departureDate=departureDate,
                            transportPerPerson=transportPerPerson,hotelPerRoomNight=hotelPerRoomNight)
    except ValidationError:
        raise HTTPException(422, '여행 카테고리, 출발 지역 또는 여행 날짜를 확인해주세요.') from None
    validate_country_filter(category, countryCode)
    async def find_affordable():
        if budget is None:
            for _ in range(3):
                candidate = await random_destination(category,countryCode) if countryCode else await random_destination(category)
                if not filter_country([candidate],countryCode):
                    continue
                verified = await confirmed_destinations([priced_city(candidate,options)],days=days,limit=1)
                if verified:
                    return verified[0],verified[0]
            raise HTTPException(404,'선택한 기간의 일정을 만들 만큼 관광명소가 충분한 여행지를 찾지 못했어요. 여행 기간을 줄이거나 국가·조건을 바꿔주세요.')
        candidates = await budget_candidates(category,countryCode) if countryCode else await budget_candidates(category)
        candidates = filter_country([*region_history(EXTERNAL_CITIES.values()), *candidates],countryCode)
        affordable=choose_budget_destinations(candidates,options,budget,category)
        verified=await confirmed_destinations([priced for _,priced in affordable],days=days)
        if not verified:
            raise HTTPException(404,'예산 안에서 선택한 기간의 일정을 만들 만큼 관광명소가 충분한 여행지를 찾지 못했어요. 여행 기간을 줄이거나 국가·예산을 바꿔주세요.')
        return choose_budget_destination(verified, options, budget, category)
    try:
        city,priced = await asyncio.wait_for(find_affordable(), timeout=55)
    except asyncio.TimeoutError:
        raise HTTPException(504, "랜덤 여행지 조회 시간이 초과됐어요. 다시 시도해주세요.") from None
    priced=await localize_destination_label(priced, allow_original=True)
    EXTERNAL_CITIES[city["cityName"]] = priced
    EXTERNAL_CITIES.move_to_end(city["cityName"])
    while len(EXTERNAL_CITIES) > 1000:
        EXTERNAL_CITIES.popitem(last=False)
    return {"city":priced,"budget":budget,"budgetBasis":"upperEstimate" if budget is not None else "unrestricted"}

class DisplayNameRequest(BaseModel):
    cityName: str = Field(min_length=1,max_length=200)
    lat: float = Field(ge=-90,le=90,allow_inf_nan=False)
    lng: float = Field(ge=-180,le=180,allow_inf_nan=False)
    countryCode: str = Field(default='',max_length=2)
    category: Literal['domestic','international'] = 'international'

@app.post('/api/destinations/display-name')
async def destination_display_name(request: DisplayNameRequest):
    stored=EXTERNAL_CITIES.get(request.cityName)
    require_destination(stored or request.model_dump())
    result=await localize_destination_label(stored or request.model_dump(), allow_original=True)
    fields=('displayName','originalName','nameTranslationNotice','nameLocalized','namePolicy')
    return {key:result[key] for key in fields if key in result}

@app.get('/api/trip-options')
def trip_options():
    return {'origins':[{'value':key,'label':value[0]} for key,value in ORIGINS.items()]}

class EstimateRequest(TripOptions):
    model_config = ConfigDict(extra='forbid')
    cityName: str = Field(min_length=1,max_length=200)

@app.post('/api/estimate')
def cost_estimate(request: EstimateRequest):
    city=EXTERNAL_CITIES.get(request.cityName) or next((c for c in CITIES if c['cityName']==request.cityName),None)
    if city is None: raise HTTPException(404,'여행지를 다시 뽑아주세요.')
    require_destination(city)
    return estimate(city,request)

@app.get("/api/destinations/search")
async def destination_search(q: str = Query(min_length=2, max_length=100),
                             category: Literal["domestic", "international"] = "domestic",
                             days: int = Query(default=3,ge=1,le=14)):
    if len(q.strip()) < 2:
        raise HTTPException(422, "검색어는 두 글자 이상 입력해주세요.")
    found = await confirmed_destinations(filter_country(await search_destinations(q.strip(), category), None),days=days,limit=12)
    for city in found:
        EXTERNAL_CITIES[city["cityName"]] = city
        EXTERNAL_CITIES.move_to_end(city["cityName"])
    while len(EXTERNAL_CITIES) > 1000:
        EXTERNAL_CITIES.popitem(last=False)
    return {"cities": [priced_city(city,TripOptions(days=days)) for city in found], "message": f"{len(found)}개 여행지를 찾았어요."}

@app.get("/api/health")
def health():
    return {"status": "ok", "aiConfigured": bool(configured_keys()),
            "demoMode": os.getenv("DEMO_MODE", "false").lower() == "true"}

@app.get("/api/cities")
def cities(category: Literal["all", "domestic", "international"] = "all"):
    return filter_cities(category)

@app.post("/api/recommend")
async def recommendations(request: RecommendRequest):
    candidates = filter_cities(request.category)
    if request.destinationNames is not None:
        known = {c["cityName"]: c for c in [*CITIES, *EXTERNAL_CITIES.values()]}
        if any(name not in known for name in request.destinationNames):
            raise HTTPException(409, "검색 결과가 만료됐어요. 여행지를 다시 검색해주세요.")
        candidates = [known[name] for name in dict.fromkeys(request.destinationNames)
                      if request.category == "all" or known[name]["category"] == request.category]
    candidates = await confirmed_destinations(filter_country(candidates, None),days=request.days)
    selected = recommend([priced_city(city,request) for city in candidates], request.budget)
    return {"cities": selected, "totalCost": sum(c["estimatedCost"] for c in selected),
            "totalSatisfaction": sum(c["satisfaction"] for c in selected),
            "message": f"{len(selected)}개 후보를 찾았어요." if selected else "예산에 맞는 도시가 없어요."}

@app.post("/api/generate-itinerary")
async def itinerary(request: ItineraryRequest):
    city = EXTERNAL_CITIES.get(request.cityName) or next((c for c in CITIES if c["cityName"] == request.cityName), None)
    if city is None:
        raise HTTPException(404, "지원하지 않는 도시입니다.")
    require_destination(city)
    if os.getenv("DEMO_MODE", "false").lower() == "true":
        places = city.get('recommendedPlaces') or [city['cityName'].split(' · ')[0]]
        days = [f"DAY {i+1} · {places[i % len(places)]}\n오전: 주변 산책 및 명소 방문\n오후: 지역 문화 체험\n저녁: 현지 식사와 휴식"
                for i in range(request.days)]
        return {"text": "\n\n".join(days) + "\n\n이 일정은 연결 확인용 고정 샘플이며 AI 생성 결과가 아닙니다.",
                "source": "demo", "cityName": city["cityName"]}
    keys = configured_keys()
    if not keys:
        raise HTTPException(503, "AI API 키가 설정되지 않았습니다. backend/.env의 GEMINI_API_KEYS 또는 GEMINI_API_KEY를 설정해주세요.")
    try:
        text = await compact_plan(city, request, None,
            os.getenv("GEMINI_ITINERARY_MODEL", "").strip() or os.getenv("GEMINI_MODEL", "").strip() or "gemini-3.1-flash-lite",
            keys)
        cost = estimate(city, request)
        summary = (f"예상 경비 {cost['total']:,}원 · {request.people}명 전체 · "
                   f"{ORIGINS[request.origin][0]} 출발\n")
        if request.budget < cost['high']:
            summary += f"예상 상한 대비 {cost['high']-request.budget:,}원 부족 · 기간이나 교통·숙박 조건을 조정해주세요.\n"
        text = summary + "\n" + text + "\n\n예상 경비는 참고용입니다. 실제 요금·운영시간·이동 경로는 예약 전 확인해주세요."
        return {"text": text, "source": "gemini", "cityName": city["cityName"]}
    except (asyncio.TimeoutError, google_errors.DeadlineExceeded):
        raise HTTPException(504, "Gemini 응답 시간이 초과되었어요. 다시 시도해주세요.")
    except google_errors.ResourceExhausted:
        raise HTTPException(429, "Gemini 사용 한도에 도달했어요. 무료 할당량과 요청 제한을 확인해주세요.")
    except google_errors.NotFound:
        raise HTTPException(502, "Gemini 모델을 사용할 수 없어요. Gemini 1.5 계열은 제공이 종료되었습니다. backend/.env의 GEMINI_MODEL을 사용 가능한 모델로 변경해주세요.")
    except (google_errors.PermissionDenied, google_errors.Unauthenticated):
        raise HTTPException(502, "Gemini 인증에 실패했어요. GEMINI_API_KEY와 프로젝트 권한을 확인해주세요.")
    except google_errors.GoogleAPICallError:
        raise HTTPException(502, "Gemini 서비스 연결에 실패했어요. API 키와 모델 설정을 확인해주세요.")


install_travel_features(app, EXTERNAL_CITIES, CITIES)
install_web(app)
