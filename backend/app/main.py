import asyncio
import json
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict
from dotenv import load_dotenv
import google.generativeai as genai
from google.api_core import exceptions as google_errors
from .optimizer import recommend

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
CITIES = json.loads((ROOT / "cities.json").read_text(encoding="utf-8"))
app = FastAPI(title="TripBudget API", version="1.0.0")
origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173")
app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in origins.split(",") if x.strip()],
                   allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

class BudgetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    budget: int = Field(gt=0, le=100_000_000, strict=True)

class ItineraryRequest(BudgetRequest):
    cityName: str = Field(min_length=1, max_length=100)

@app.get("/api/health")
def health():
    return {"status": "ok", "aiConfigured": bool(os.getenv("GEMINI_API_KEY", "").strip()),
            "demoMode": os.getenv("DEMO_MODE", "false").lower() == "true"}

@app.get("/api/cities")
def cities():
    return CITIES

@app.post("/api/recommend")
def recommendations(request: BudgetRequest):
    selected = recommend(CITIES, request.budget)
    return {"cities": selected, "totalCost": sum(c["estimatedCost"] for c in selected),
            "totalSatisfaction": sum(c["satisfaction"] for c in selected),
            "message": f"{len(selected)}개 후보를 찾았어요." if selected else "예산에 맞는 도시가 없어요."}

@app.post("/api/generate-itinerary")
async def itinerary(request: ItineraryRequest):
    city = next((c for c in CITIES if c["cityName"] == request.cityName), None)
    if city is None:
        raise HTTPException(404, "지원하지 않는 도시입니다.")
    if os.getenv("DEMO_MODE", "false").lower() == "true":
        days = [f"DAY {i+1} · {place}\n오전: 주변 산책 및 명소 방문\n오후: 지역 문화 체험\n저녁: 현지 식사와 휴식"
                for i, place in enumerate(city["recommendedPlaces"][:3])]
        return {"text": "\n\n".join(days) + "\n\n이 일정은 연결 확인용 고정 샘플이며 AI 생성 결과가 아닙니다.",
                "source": "demo", "cityName": city["cityName"]}
    if not os.getenv("GEMINI_API_KEY", "").strip():
        raise HTTPException(503, "AI API 키가 설정되지 않았습니다. backend/.env의 GEMINI_API_KEY를 설정해주세요.")
    try:
        genai.configure(api_key=os.environ["GEMINI_API_KEY"].strip())
        model = genai.GenerativeModel(
            model_name=os.getenv("GEMINI_MODEL", "").strip() or "gemini-1.5-flash-latest",
            system_instruction="한국어 여행 플래너입니다. 1인 3일 여행을 DAY 1~3으로 작성하세요. 매일 오전/오후/저녁, 이동 방법, 예상 비용을 포함하세요. 항공·숙박·식비·교통·입장료 예산표와 합계도 작성하세요. 예산이 부족하면 명확히 밝히고 대안을 제시하세요. 금액은 추정이며 실시간 가격이 아님을 명시하세요. 마크다운 표 없이 읽기 쉬운 일반 텍스트, 1800자 이내로 작성하세요.",
        )
        response = await asyncio.wait_for(
            model.generate_content_async(
                json.dumps({"city": city["cityName"], "budgetKRW": request.budget,
                            "places": city["recommendedPlaces"]}, ensure_ascii=False),
                generation_config={"max_output_tokens": 3000, "temperature": 0.7},
                request_options={"timeout": 45, "retry": None},
            ),
            timeout=50,
        )
        # STOP=1. Blocked, truncated and empty candidates must not look like complete itineraries.
        if not response.candidates or response.candidates[0].finish_reason != 1:
            raise HTTPException(502, "Gemini 일정 생성이 완료되지 않았거나 차단됐어요. 다시 시도해주세요.")
        try:
            text = response.text.strip()
        except (ValueError, AttributeError):
            text = ""
        if not text:
            raise HTTPException(502, "Gemini가 빈 일정을 반환했어요. 다시 시도해주세요.")
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
