# TripBudget — 생성형 AI 듀얼 트랙 여행 추천기

React + Vite + Tailwind CSS + React-Leaflet + Framer Motion / FastAPI + Google Gemini API.

## 빠른 실행 (Windows PowerShell)

```powershell
cd C:\gitpractice\TripBudget
powershell -ExecutionPolicy Bypass -File .\setup.ps1
# backend/.env에 GEMINI_API_KEY 입력 (채팅이나 프론트엔드에 키를 넣지 마세요)
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

브라우저: http://127.0.0.1:5173  
API 문서: http://127.0.0.1:8000/docs  
종료: 실행 터미널에서 Ctrl+C.

키 없이 기능을 시연하려면:
```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1 -Demo
```
이 모드에서는 **샘플 일정 · AI 생성 아님** 배지가 표시됩니다. 실제 생성형 AI 시연에는 유효한 API 키와 사용 가능한 모델/결제 설정이 필요합니다. 키가 없을 때 실제 AI 모드는 503 안내를 반환합니다.

## 프로젝트 구조

- frontend/src/App.jsx: 모드 전환, 예산 추천, 요청 취소, 초기화
- frontend/src/components/TravelMap.jsx: 지도, 포물선 다트, 축하 효과
- frontend/src/components/Itinerary.jsx: AI 결과, 타자기 효과, 재시도
- frontend/src/api.js: API 호출, 제한시간, 오류 처리
- backend/app/main.py: FastAPI 엔드포인트와 LLM 연동
- backend/app/optimizer.py: 개수 제한 0/1 배낭 동적 계획법
- backend/cities.json: 15개 도시, 1인 3일 예상 경비, 관광지, 만족도
- backend/tests/test_api.py: 알고리즘 최적성 및 API 테스트
- legacy/index.html: 이전 단일 HTML 버전 보관

## 추천 알고리즘 정의

도시는 중복 선택할 수 없습니다. 비용 합계가 예산 이하인 **후보 도시 3개 조합** 중 만족도 합계가 가장 높은 조합을 반환합니다. 3개를 담을 수 없으면 가능한 최대 개수(2/1/0)를 선택합니다. 동점이면 더 저렴한 조합을 선택합니다.

원 단위 비용과 개수를 키로 하는 희소 DP를 사용합니다. 각 도시를 한 번씩 처리하므로 0/1 배낭 조건을 지킵니다. 15개 도시·최대 3개 선택에 적합하며, 무제한 카탈로그용 알고리즘은 아닙니다.

세 도시는 한 번에 방문하는 이동 경로가 아닌 후보 목록입니다. 모드 A 일정은 사용자가 입력한 전체 예산으로 선택 도시 하나의 3일 일정을 만듭니다. 모드 B는 무작위 도시의 예상 경비를 일정 생성 예산으로 사용합니다. 만족도 점수·경비는 시연용 가상 데이터이며 실시간 가격이나 개인화 점수가 아닙니다.

## 환경변수

backend/.env:
- GEMINI_API_KEY: 실제 AI 생성에 필수
- GEMINI_MODEL: 요청된 기본값 gemini-1.5-flash-latest. 제공 종료된 모델이므로 실제 AI 생성에는 계정에서 사용 가능한 모델로 변경 필요
- DEMO_MODE: 명시적으로 true일 때 샘플 반환 (start.ps1은 -Demo로 제어)
- CORS_ORIGINS: 쉼표 구분 origin 목록, 기본 localhost/127.0.0.1의 5173·4173

frontend/.env:
- VITE_API_BASE_URL: 기본 빈 값. Vite가 /api를 127.0.0.1:8000으로 프록시합니다.
- 프론트엔드 환경변수에는 비밀 키를 넣지 않습니다.

## 수동 실행 / macOS·Linux

Python 3.11+ 및 Node 22.12+ 필요.
```bash
cd backend
python -m venv .venv
# Windows: .venv/Scripts/activate
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# .env 편집 후
uvicorn app.main:app --host 127.0.0.1 --port 8000
```
별도 터미널:
```bash
cd frontend
npm install
npm run dev
```

## API

- GET /api/health: 서버 및 AI 설정 상태 (외부 API 인증 성공을 보장하지 않음)
- GET /api/cities: 전체 도시 목록
- POST /api/recommend: {"budget":1500000}
- POST /api/generate-itinerary: {"cityName":"부산 · 대한민국","budget":500000}

예산은 1~100,000,000 정수 원. 등록되지 않은 도시는 404.
LLM 누락 키 503, 시간 초과 504, 사용 한도 429, 공급자 오류/미완료 502.
모드 전환과 초기화는 진행 중인 UI 요청과 애니메이션을 무효화합니다. 이미 공급자에 전송한 요청은 취소 후에도 요금이 발생할 수 있습니다.

## 검증

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
cd ../frontend
npm run build
```

테스트는 작은 데이터의 완전 탐색 결과와 DP를 비교하고, CORS·입력 검증·누락 키·데모 표시·모의 LLM 응답을 확인합니다. 실제 LLM 호출 검증은 별도 유효 키가 필요합니다.

실제 AI 호출: Google Gemini API (google-generativeai 0.8.5).
지도 타일은 OpenStreetMap 인터넷 연결을 사용합니다. 로컬 부스 시연용이며 공개 배포 전에는 인증·요청 제한·비용 제한을 추가해야 합니다.

## Gemini 전환 안내

요청된 기본 모델은 gemini-1.5-flash-latest입니다. Gemini 1.5 Flash 및 Pro 계열은 2025-09-29 종료되어, latest 별칭이나 gemini-1.5-pro로 변경해도 실제 API 호출 성공을 보장할 수 없습니다. 서버 기동과 모델 객체 생성은 외부 API 호출 성공과 별개입니다. 실제 생성에는 GEMINI_API_KEY와 함께 GEMINI_MODEL을 계정에서 사용할 수 있는 모델로 변경해야 합니다. 모델을 자동으로 대체하지 않습니다. 무료 사용 여부는 선택 모델·프로젝트의 할당량 및 결제 설정에 따라 달라집니다.

google-generativeai는 요청에 따라 사용한 레거시 SDK입니다. 공식 권장 SDK는 google-genai입니다. 기존 프론트엔드는 변경하지 않았으며 응답은 {text, source: "gemini", cityName}입니다.

공식 안내: https://ai.google.dev/gemini-api/docs/changelog#september-29-2025 및 https://ai.google.dev/gemini-api/docs/libraries
