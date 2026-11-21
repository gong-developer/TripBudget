"""Check configured Gemini keys without generating text or printing secrets."""
import os
from pathlib import Path
import sys

import httpx
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.gemini_keys import configured_keys, provider_failure


def main():
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
    keys = configured_keys()
    model = (os.getenv('GEMINI_ITINERARY_MODEL', '').strip() or os.getenv('GEMINI_MODEL', '').strip() or 'gemini-3.1-flash-lite').removeprefix('models/')
    if not keys:
        print('GEMINI_API_KEYS 또는 GEMINI_API_KEY를 설정해주세요.')
        return 1
    print(f'등록 키 {len(keys)}개 · 일정 모델 {model}')
    available = False
    for index, key in enumerate(keys, 1):
        try:
            response = httpx.get(f'https://generativelanguage.googleapis.com/v1beta/models/{model}',
                                 headers={'x-goog-api-key':key}, timeout=15)
            if response.is_success:
                available = True
                print(f'키 {index}: 모델 접근 정상 (HTTP {response.status_code})')
            else:
                print(f'키 {index}: HTTP {response.status_code} · {provider_failure(response).detail}')
        except httpx.TimeoutException:
            print(f'키 {index}: 연결 시간 초과')
        except httpx.RequestError:
            print(f'키 {index}: 네트워크·DNS 연결 실패')
    print('모델 접근 검사만 수행했습니다. 생성 요청의 남은 할당량을 보장하지는 않습니다.')
    return 0 if available else 1


if __name__ == '__main__':
    sys.exit(main())
