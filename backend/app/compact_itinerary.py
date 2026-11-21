"""Small reusable route plans. Costs and presentation stay outside the model."""
import asyncio
import json
import logging
import os
import time
from collections import OrderedDict

from fastapi import HTTPException
import httpx
from .korean_itinerary import has_foreign_words
from .itinerary_context import prepare_itinerary
from .quality_itinerary import render_quality_plan, quality_instruction
from .costs import ALIASES
from .place_names import NAME_POLICY
from .travel_themes import theme_instruction
from .gemini_keys import GeminiFailure, pool_id, provider_failure, with_key_failover

log = logging.getLogger(__name__)
CACHE = OrderedDict()
INFLIGHT = {}
TTL = 6 * 60 * 60
LIMIT = 256
VERSION = 8


def thinking_level(model_name):
    if not model_name.removeprefix('models/').startswith('gemini-3'):
        return None
    lite = 'flash-lite' in model_name
    default = 'minimal' if lite else 'low'
    value = os.getenv('GEMINI_ITINERARY_THINKING_LEVEL', default).strip().lower()
    allowed = ('minimal', 'low', 'medium', 'high') if lite else ('low', 'medium', 'high')
    return value if value in allowed else default


def plan_input(city, request):
    # Full estimates, prices, people and origin do not affect this local route.
    places = [] if city.get('destinationType') == 'region' else list(dict.fromkeys(city.get('recommendedPlaces', [])))[:24]
    label=city.get('displayName') if city.get('namePolicy')==NAME_POLICY else None
    if not label and city.get('originalName'):
        label=' · '.join([city['originalName'],*city['cityName'].split(' · ')[1:]])
    return {**({'destinationType':'region', 'originalName':city.get('originalName') or city['cityName'].split(' · ')[0],
                **({'regionId':city['regionId']} if city.get('regionId') else {})} if city.get('destinationType') == 'region' else {}),
            'city': label or city['cityName'], 'days': request.days,
            'location':[city['lat'],city['lng']],
            'countryCode':city.get('countryCode') or ('kr' if city.get('category')=='domestic' else next((code for name,code in ALIASES.items() if name in city['cityName']),'')),
            'style': request.style, 'theme': request.selected_themes[0] if request.selected_themes else None, 'themes': request.selected_themes, 'date': str(request.departureDate) if request.departureDate else None,
            'places': places}


def render_plan(raw, data):
    try:
        rows = json.loads(raw)
        if not isinstance(rows, list) or len(rows) != data['days']:
            raise ValueError('Missing days')
        lines = []
        for day, slots in enumerate(rows, 1):
            if not isinstance(slots, list) or len(slots) != 3:
                raise ValueError('Missing time slots')
            lines.append(f'{day}일차')
            for label, slot in zip(('오전', '오후', '저녁'), slots):
                if not isinstance(slot, list) or len(slot) != 3:
                    raise ValueError('Invalid slot')
                place, activity, transport = slot
                if type(place) is int:
                    if not 0 <= place < len(data['places']):
                        raise ValueError('Unknown place')
                    place = data['places'][place]
                if not all(isinstance(x, str) and 0 < len(x) <= 60 for x in (place, activity, transport)):
                    raise ValueError('Invalid text')
                # Never send the whole result through a second translation call.
                if has_foreign_words(place):
                    raise ValueError('Place needs a Korean name')
                activity = activity if not has_foreign_words(activity) else '주변 명소 둘러보기'
                transport = transport if not has_foreign_words(transport) else '현지 교통 확인'
                lines.append(f'{label}: {place} · {activity} (이동: {transport})')
            lines.append('')
        return '\n'.join(lines).strip()
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(502, '일정 형식이 올바르지 않아요. 일정 생성 다시 시도를 눌러주세요.') from exc


async def compact_plan(city, request, genai, model_name, api_key):
    keys = (api_key,) if isinstance(api_key, str) else tuple(api_key)
    data = plan_input(city, request)
    payload = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    level = thinking_level(model_name)
    key = (VERSION, model_name, level, pool_id(keys), payload)
    now = time.monotonic()
    for old_key, (expiry, _) in list(CACHE.items()):
        if expiry <= now:
            CACHE.pop(old_key, None)
    if key in CACHE and not getattr(request,'refresh',False):
        CACHE.move_to_end(key)
        return CACHE[key][1]
    task = INFLIGHT.get(key)
    if task is None:
        task = asyncio.create_task(_generate(data, payload, genai, model_name, keys, level))
        INFLIGHT[key] = task

        def finished(done):
            if INFLIGHT.get(key) is done:
                INFLIGHT.pop(key, None)
            if not done.cancelled() and done.exception() is None:
                CACHE[key] = (time.monotonic() + TTL, done.result())
                CACHE.move_to_end(key)
                while len(CACHE) > LIMIT:
                    CACHE.popitem(last=False)

        task.add_done_callback(finished)
    # A browser disconnect must not cause a second paid request for the same plan.
    return await asyncio.shield(task)


async def _generate(data, payload, genai, model_name, api_key, level):
    async with asyncio.timeout(90):
        return await _generate_bounded(data, genai, model_name, api_key, level)


async def _generate_bounded(data, genai, model_name, keys, level):
    data = await prepare_itinerary(data)
    data = {**data, 'places':[{**place, 'id':index} for index, place in enumerate(data['places'])]}
    priorities = [place['id'] for place in data['places'] if place.get('priority')]
    data['requiredHighlights'] = {'placeIds':priorities, 'minimum':min(data['days'], len(priorities))}
    payload = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    instruction = quality_instruction(data['days']) + theme_instruction(data.get('themes',[data.get('theme','sightseeing')]))
    if level or genai is None:
        async def generate(key):
            return await _generate_with_retry(payload, instruction, model_name, key, level, data['days'])
        raw = await with_key_failover(keys, model_name, generate)
        return render_quality_plan(raw, data)
    model = genai.GenerativeModel(model_name=model_name, system_instruction=instruction)
    response = await asyncio.wait_for(model.generate_content_async(
        payload, generation_config={'max_output_tokens': max(4096,1024+data['days']*900),
                                    'temperature': 0.4, 'response_mime_type': 'application/json'},
        request_options={'timeout': 45, 'retry': None}), timeout=50)
    usage = getattr(response, 'usage_metadata', None)
    if usage:
        log.info('itinerary tokens input=%s output=%s total=%s',
                 getattr(usage, 'prompt_token_count', None),
                 getattr(usage, 'candidates_token_count', None),
                 getattr(usage, 'total_token_count', None))
    if not response.candidates or response.candidates[0].finish_reason != 1:
        raise HTTPException(502, 'Gemini 일정 생성이 완료되지 않았거나 차단됐어요. 다시 시도해주세요.')
    try:
        raw = response.text.strip()
    except (ValueError, AttributeError):
        raw = ''
    return render_quality_plan(raw, data)


async def _generate_with_retry(payload, instruction, model_name, api_key, level, days):
    # Retry only explicit overload responses. Timeouts may have already generated
    # a paid result, and authentication/format failures need a different remedy.
    for attempt in range(3):
        try:
            return await _generate_fast(payload, instruction, model_name, api_key, level, days)
        except GeminiFailure as error:
            if error.status_code != 503 or attempt == 2:
                raise
            delay = 2 ** attempt
            log.info('itinerary provider unavailable model=%s retry=%d delay_seconds=%d',
                     model_name, attempt + 1, delay)
            await asyncio.sleep(delay)


async def _generate_fast(payload, instruction, model_name, api_key, level, days):
    """Use the documented REST field absent from the legacy SDK's protobuf."""
    started = time.monotonic()
    model = model_name.removeprefix('models/')
    body = {
        'systemInstruction': {'parts': [{'text': instruction}]},
        'contents': [{'role': 'user', 'parts': [{'text': payload}]}],
        'generationConfig': {
            **({'thinkingConfig': {'thinkingLevel': level}} if level else {}),
            'responseMimeType': 'application/json',
            # Gemini 3 counts thinking against this budget too. Leave enough room
            # for all requested days, rather than silently truncating the JSON.
            'maxOutputTokens': max(4096, 1024 + days * 900),
        },
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(45, connect=8)) as client:
            response = await client.post(
                f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
                headers={'x-goog-api-key': api_key}, json=body)
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, dict):
                raise ValueError('Invalid response object')
    except httpx.TimeoutException:
        raise HTTPException(504, 'Gemini 응답 시간이 초과되었어요. 다시 시도해주세요.') from None
    except httpx.HTTPStatusError as error:
        raise provider_failure(error.response) from None
    except httpx.RequestError:
        raise HTTPException(502, 'Gemini 서버에 연결할 수 없어요. 서버의 인터넷·DNS 연결을 확인해주세요.') from None
    except ValueError:
        raise HTTPException(502, 'Gemini 응답 형식을 읽지 못했어요. 다시 시도해주세요.') from None
    usage = result.get('usageMetadata') or {}
    if not isinstance(usage, dict):
        usage = {}
    log.info('itinerary model=%s thinking=%s seconds=%.2f input=%s output=%s thought=%s total=%s',
             model, level, time.monotonic()-started, usage.get('promptTokenCount'),
             usage.get('candidatesTokenCount'), usage.get('thoughtsTokenCount'), usage.get('totalTokenCount'))
    candidates = result.get('candidates') or []
    if not isinstance(candidates, list) or not candidates or not isinstance(candidates[0], dict) or candidates[0].get('finishReason') != 'STOP':
        raise HTTPException(502, 'Gemini 일정 생성이 완료되지 않았거나 차단됐어요. 다시 시도해주세요.')
    content = candidates[0].get('content')
    parts = content.get('parts') if isinstance(content, dict) else None
    if not isinstance(parts, list) or any(not isinstance(part, dict) or not isinstance(part.get('text', ''), str) for part in parts):
        raise HTTPException(502, 'Gemini 일정 응답을 읽지 못했어요. 다시 시도해주세요.')
    return ''.join(part.get('text', '') for part in parts if not part.get('thought')).strip()
