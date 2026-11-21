# 노트북으로 옮겨 실행하기

이 압축 파일은 현재 TripBudget 웹사이트의 소스, Git 기록, 설치 잠금 파일, 지도·도시 데이터, 빌드된 웹 화면, 기존 API 설정(`backend/.env`)을 포함합니다. 개인용 이전 파일이며 실제 API 키가 들어 있으므로 본인 기기에 보관하세요.

## Windows 노트북

1. 압축을 완전히 풀고 `TripBudget` 폴더를 여세요.
2. Node.js 22.12 이상과 npm이 설치되어 있어야 합니다. PowerShell에서 `node --version`, `npm.cmd --version`으로 확인하세요.
3. 해당 폴더에서 아래 명령을 실행하세요. 인터넷 연결이 필요합니다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1
```

Windows용 uv 도구를 함께 넣었습니다. `setup.ps1`이 프로젝트 안에 Python 3.12 환경을 새로 만들고 필요한 Python·npm 패키지를 설치합니다. 기존 API 키는 `backend/.env`에 포함되어 있어 다시 입력할 필요가 없습니다.

실행 후 `http://127.0.0.1:5173`을 여세요. 서버와 화면을 실행한 PowerShell 창은 사용 중 유지하세요. 종료는 `Ctrl+C`입니다. API 문서는 `http://127.0.0.1:8000/docs`에서 확인할 수 있습니다.

## macOS / Linux 노트북

Python 3.12와 Node.js 22.12 이상이 설치된 환경에서:

```sh
cd TripBudget
python3.12 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.lock
cd frontend
npm ci
cd ..
```

터미널 두 개에서 각각 실행하세요:

```sh
cd TripBudget/backend
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```sh
cd TripBudget/frontend
npm run dev
```

Windows 전용 `uv.exe`는 macOS/Linux에서 사용하지 않습니다. 위 수동 설치 절차를 사용하세요.

## 이전되는 데이터

- 현재 수정 사항을 포함한 전체 웹사이트 소스와 Git 기록
- 현재 Gemini·외부 API 설정
- 국가 경계와 세계 도시 카탈로그
- 서버에서 보관하던 여행지 데이터 (`.tools/destinations.sqlite3`, SQLite 백업 방식으로 복사)
- 현재 빌드된 웹 화면 (`frontend/dist`)

## 여행 계획은 브라우저에서 별도 백업

‘저장한 여행 계획’은 PC의 브라우저 저장소에 있어 이 압축 파일에 들어 있지 않습니다. 기존 PC에서 웹사이트를 열어 **저장한 여행 계획 → 계획 백업**으로 JSON 파일을 저장하고, 노트북에서 **백업 불러오기**로 가져오세요.

설치된 `node_modules`, Python 가상환경, 다운로드 캐시, 번역 서버 설치 파일, 로그, 일시적인 API 요청 제한 기록은 제외했습니다. 이전 PC의 절대 경로가 들어 있는 설치 환경을 복사하지 않고 노트북에서 다시 구성합니다. 휴대폰 앱 파일은 제거된 상태입니다.
