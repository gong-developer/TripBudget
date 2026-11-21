# TripBudget

예산에 맞는 여행지를 비교하고 한국어 AI 일정을 만드는 웹앱입니다.

## 주요 기능

- 예산·국가·기간·인원·출발 지역에 따른 여행지 후보 비교와 랜덤 룰렛 추천
- 휴양·관광·맛집·액티비티·쇼핑·자연/트레킹·감성사진을 버튼으로 복수 선택하고 예상 경비·AI 일정에 반영
- 실제 관광명소가 확인된 여행지만 추천·룰렛에 표시, 명소 없는 지역은 제외
- 북한과 전역 여행금지 10개국 추천·검색·국가 선택 제외 (2026-11-04 외교부 확인, backend/app/travel_policy.py 관리)
- 금액대별 새로고침으로 같은 금액대의 다른 여행지 후보 재추천
- 지도·조건 검색 화면과 추천 결과 화면 분리, 결과 화면에서 여행지·명소·AI 일정 탭으로 이동
- 국내는 TourAPI 지역 내 명소 사진 우선, 해외는 Unsplash 대표 사진 우선 및 Commons 대체 사진, 위치 확인과 사진가·출처 제공
- 국내는 시·군 등 행정지역, 해외는 도시 단위 지역을 먼저 선택하고 일정 생성 시 해당 지역의 명소를 조회
- 국가 선택 지도와 주변 명소, 등록된 한국어 지명 우선 표시와 원어 보존
- 빠른 Gemini 일정 생성, 경과 시간 표시·취소·같은 조건의 결과 재사용
- 항목별 계획용 예상 경비와 사용자 확인 교통·숙박 가격 반영
- 브라우저에 최근 20개 계획 저장, JSON 백업·복원
- 외부 기능 요청 횟수·일일 사용량·본문 크기·동시 처리 제한
- 서버 재시작 후에도 여행지와 요청 제한 데이터 유지

날짜별 일정의 지도 경로 표시는 제공하지 않습니다. 경비는 실시간 예약 가격이 아닌 계획용 추정입니다. 지명 자동 번역을 중단했으며 확인되지 않은 이름은 원어로 유지합니다.

## 개발 실행

Python 3.12와 Node.js 22.12 이상을 사용합니다.

```powershell
cd C:\Tripbudget\TripBudget
powershell -ExecutionPolicy Bypass -File .\setup.ps1
# backend/.env에 필요한 서버용 API 키 설정
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

개발 화면은 http://127.0.0.1:5173, API 문서는 http://127.0.0.1:8000/docs 입니다.
키는 서버의 환경 변수에만 보관합니다. 프론트엔드나 Git에 넣지 않습니다.

AI 일정에는 Gemini 키, 여행지·명소 검색에는 Geoapify와 TourAPI 키가 필요합니다.
`-Demo`는 AI 일정만 샘플로 바꾸며 외부 여행지 조회를 오프라인으로 대체하지 않습니다.

## 지명 표시

공급자·등록 지명 사전의 한국어 이름을 우선하며 미등록 이름은 원어를 표시합니다. LibreTranslate와 Gemini의 지명 자동 번역, 기존 자동 번역 캐시는 사용하지 않습니다. 번역 서버를 설치하거나 실행할 필요가 없습니다.

기존 저장 계획의 불확실한 일정 원문은 백업에 보존하고 새로 생성할 수 있습니다. 정책과 캐시 무효화는 [MAP_LANGUAGE.md](MAP_LANGUAGE.md)에 정리돼 있습니다.

## 운영 구성

[DEPLOYMENT.md](DEPLOYMENT.md)를 기준으로 준비합니다.
Docker Compose 구성은 웹 빌드·API와 영구 데이터 볼륨을 포함합니다. 이전 번역 서버는 수동 실험 프로필로만 남겨 기본 실행에서 제외합니다.
개발 서버를 그대로 외부에 공개하지 않습니다.

공개 배포는 아직 수행하지 않았으며 Docker 실행, 실제 휴대폰 화면, HTTPS·프록시·부하 검증이 남아 있습니다.
기본 보호 설정은 소규모 베타용이며 공급자 과금 상한이나 대규모 공격 방어를 보장하지 않습니다.

## 검증

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
cd ../frontend
node --test tests/*.test.js
npm run build
```

백엔드의 검증한 패키지 버전은 `requirements.lock`, 프론트엔드는 `package-lock.json`에 고정합니다.

## 구현 안내

- [AI_TOKEN_USAGE.md](AI_TOKEN_USAGE.md): 모델 설정, 지연 개선, 캐시, 실측 도구
- [MAP_LANGUAGE.md](MAP_LANGUAGE.md): 지도·추천 여행지·주변 명소의 지명 처리
- [DEPLOYMENT.md](DEPLOYMENT.md): 운영 실행, 데이터 유지, 요청 제한, 남은 검증
- `backend/app/main.py`: 여행지·경비·AI API
- `backend/app/protection.py`: 요청 제한과 보안 헤더
- `backend/app/storage.py`: SQLite 영구 여행지 저장
- `frontend/src/App.jsx`: 여행 계획 화면과 요청·저장 상태 관리
