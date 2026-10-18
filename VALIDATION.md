# Gemini 전환 검증

- google-generativeai 0.8.5 설치, OpenAI 패키지 제거 완료
- pytest: 33 passed (기존 알고리즘·CORS·검증 및 Gemini 성공/예외/빈 응답 계약, 기본 모델·빈 설정·Pro 설정 확인)
- 실제 Uvicorn 일반 모드 HTTP: health 200, recommend 200, 키 미설정 일정 요청 503
- 실제 Uvicorn 데모 모드 HTTP: health 200, recommend 200, 샘플 일정 200
- 검증용 서버는 종료됨
- 프론트엔드 파일 변경 없음. 응답 text/source/cityName 유지, 실제 생성 source는 gemini
- 코드 기본값, .env.example, 로컬 .env 모델명: gemini-1.5-flash-latest. 기존 API 키는 유지
- 실제 Gemini 생성: 미검증. Gemini 1.5 계열은 제공 종료 모델이므로 키만 입력해서 실제 생성 성공을 보장할 수 없음. 사용 가능한 GEMINI_MODEL 설정 필요
- Starlette TestClient의 httpx 사용 중단 예정 경고 1개, 테스트 정상 통과

재실행: backend에서 .\.venv\Scripts\python.exe -m pytest -q 및 .\.venv\Scripts\python.exe scripts\smoke_test.py
