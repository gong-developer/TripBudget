"""Bounded quota failover for explicitly configured Gemini credentials."""
from collections import OrderedDict
from datetime import datetime, time as day_time, timedelta, timezone
from email.utils import parsedate_to_datetime
import hashlib
import logging
import math
import os
import re
import time
from zoneinfo import ZoneInfo
from fastapi import HTTPException

log = logging.getLogger(__name__)
COOLDOWNS = OrderedDict()
ACTIVE = OrderedDict()
LIMIT = 256


def configured_keys():
    listed = tuple(dict.fromkeys(part.strip() for part in re.split(r'[,;\s]+', os.getenv('GEMINI_API_KEYS', '')) if part.strip()))
    single = os.getenv('GEMINI_API_KEY', '').strip()
    return listed or ((single,) if single else ())


def fingerprint(value):
    return hashlib.sha256(value.encode()).hexdigest()


def pool_id(keys):
    return fingerprint('\0'.join(keys))


class GeminiFailure(HTTPException):
    def __init__(self, status, detail, *, kind, retry_after=60):
        super().__init__(status, detail)
        self.kind = kind
        self.retry_after = retry_after


def provider_failure(response):
    try:
        error = response.json().get('error', {})
        error = error if isinstance(error, dict) else {}
    except (ValueError, AttributeError):
        error = {}
    if response.status_code == 429:
        details = error.get('details') or []
        details = details if isinstance(details, list) else []
        quotas = [str(row.get('quotaId', '')) for detail in details if isinstance(detail, dict)
                  and isinstance(detail.get('violations'), list) for row in detail['violations'] if isinstance(row, dict)]
        daily = any(token in ' '.join(quotas).lower() for token in ('perday', 'per_day', 'daily'))
        delay = 60.0
        if daily:
            now = datetime.now(ZoneInfo('America/Los_Angeles'))
            reset = datetime.combine(now.date()+timedelta(days=1), day_time(), tzinfo=now.tzinfo)
            delay = reset.timestamp()-now.timestamp()
        candidates = []
        for detail in details:
            if isinstance(detail, dict) and isinstance(detail.get('retryDelay'), str):
                try:candidates.append(float(detail['retryDelay'].removesuffix('s')))
                except ValueError:pass
        header = response.headers.get('Retry-After')
        if header:
            try:candidates.append(float(header))
            except ValueError:
                try:candidates.append(parsedate_to_datetime(header).timestamp()-datetime.now(timezone.utc).timestamp())
                except (ValueError, TypeError, OverflowError):pass
        valid = [seconds for seconds in candidates if math.isfinite(seconds) and seconds > 0]
        if valid:
            delay = max(delay if daily else 1, max(valid))
        return GeminiFailure(429, 'Gemini 사용 한도에 도달했어요. 잠시 후 다시 시도해주세요.',
                             kind='daily_quota' if daily else 'rate_limit', retry_after=max(1, delay))
    if response.status_code in (401,403):
        return GeminiFailure(502, 'Gemini API 키 인증 또는 프로젝트 접근 권한을 확인해주세요.', kind='authentication')
    if response.status_code == 404:
        return GeminiFailure(502, '설정한 Gemini 모델을 사용할 수 없어요. GEMINI_ITINERARY_MODEL 또는 GEMINI_MODEL을 확인해주세요.', kind='model')
    if response.status_code == 400:
        details = error.get('details')
        reasons = [str(detail.get('reason', '')) for detail in details if isinstance(detail, dict)] if isinstance(details, list) else []
        if any(reason.startswith('API_KEY_') for reason in reasons):
            return GeminiFailure(502, 'Gemini API 키가 올바르지 않거나 만료·차단됐어요. AI Studio에서 키 상태를 확인해주세요.', kind='authentication')
        return GeminiFailure(502, 'Gemini API 키가 유효한지, 선택한 모델이 요청 설정을 지원하는지 확인해주세요.', kind='configuration')
    if response.status_code == 402:
        return GeminiFailure(502, 'Gemini 프로젝트의 결제·사용 가능 잔액을 확인해주세요.', kind='billing')
    if response.status_code == 503:
        return GeminiFailure(503, 'Gemini 서비스가 일시적으로 혼잡해요. 잠시 후 다시 시도해주세요.', kind='unavailable')
    return GeminiFailure(502, 'Gemini 서버에서 오류가 발생했어요. 잠시 후 다시 시도해주세요.', kind='provider')


async def with_key_failover(keys, model, generate):
    keys = tuple(dict.fromkeys(keys))
    if not keys:
        raise HTTPException(503, 'backend/.env에 GEMINI_API_KEYS 또는 GEMINI_API_KEY를 설정해주세요.')
    now = time.monotonic()
    for key, (until, _) in list(COOLDOWNS.items()):
        if until <= now:
            COOLDOWNS.pop(key, None)
    pool = (pool_id(keys), model)
    preferred = ACTIVE.get(pool)
    ordered = sorted(enumerate(keys, 1), key=lambda item: fingerprint(item[1]) != preferred)
    for slot, key in ordered:
        identity = (fingerprint(key), model)
        if identity in COOLDOWNS:
            continue
        try:
            result = await generate(key)
        except GeminiFailure as error:
            if error.status_code != 429:
                raise
            COOLDOWNS[identity] = (time.monotonic()+error.retry_after, error.kind)
            while len(COOLDOWNS) > LIMIT:
                COOLDOWNS.popitem(last=False)
            log.info('Gemini quota key_slot=%d kind=%s cooldown_seconds=%d', slot, error.kind, math.ceil(error.retry_after))
            continue
        ACTIVE[pool] = fingerprint(key)
        ACTIVE.move_to_end(pool)
        while len(ACTIVE) > LIMIT:
            ACTIVE.popitem(last=False)
        return result
    waits = [COOLDOWNS[(fingerprint(key), model)][0]-time.monotonic() for key in keys if (fingerprint(key), model) in COOLDOWNS]
    delay = max(1, math.ceil(min(waits, default=60)))
    raise HTTPException(429, '등록된 Gemini 키의 사용 한도에 도달했어요. 한도 초기화 후 다시 시도하거나 사용 가능한 예비 키를 설정해주세요.', headers={'Retry-After':str(delay)})
