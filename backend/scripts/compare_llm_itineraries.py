"""Compare real providers using one frozen POI context and production validation.

Does not change the website's AI provider. Credentials are read only from env/.env.
"""
import argparse
import asyncio
import json
import logging
import os
from pathlib import Path
import sys
import time
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.main import CITIES, ItineraryRequest
from app.compact_itinerary import plan_input, thinking_level, _generate_fast
from app.itinerary_context import prepare_itinerary
from app.quality_itinerary import quality_instruction, render_quality_plan


def evaluate(raw, context):
    try:
        rendered = render_quality_plan(raw, context)
        days = json.loads(raw)['days']
        return {'validation': 'passed', 'days': len(days),
                'visits': sum(len(day['visits']) for day in days),
                'detail_characters': sum(len(visit['activity']) for day in days for visit in day['visits'])}, rendered
    except HTTPException as error:
        return {'validation': 'failed', 'reason': str(error.__cause__) or str(error.detail)}, None


async def candidate_request(base, key, model, payload, instruction, days):
    parts = urlsplit(base)
    if parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError('Use a gateway base URL without credentials or URL tokens')
    if parts.scheme != 'https' and not (parts.scheme == 'http' and parts.hostname in ('localhost', '127.0.0.1', '::1')):
        raise ValueError('Remote gateways require HTTPS')
    async with httpx.AsyncClient(timeout=httpx.Timeout(50, connect=8)) as client:
        response = await client.post(base.rstrip('/') + '/chat/completions',
            headers={'Authorization': f'Bearer {key}'},
            json={'model': model, 'messages': [
                {'role': 'system', 'content': instruction}, {'role': 'user', 'content': payload}],
                'temperature': 0.4, 'max_tokens': max(4096, 1024 + days * 900), 'stream': False})
        response.raise_for_status()
        result = response.json()
        choice = result['choices'][0]
        if choice.get('finish_reason') != 'stop':
            raise ValueError('Candidate response did not finish normally')
        text = choice['message']['content']
        if not isinstance(text, str):
            raise ValueError('Candidate returned non-text content')
        route = response.headers.get('x-routed-via')
        return text.strip(), {'routed_via': route, 'returned_model': result.get('model'),
                              'usage': result.get('usage'),
                              'independent_from_gemini': None if not route else 'gemini' not in route.casefold()}


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--city', default='부산 · 대한민국')
    parser.add_argument('--days', type=int, default=3, choices=range(1, 15))
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[2] / '.tools/llm-comparison')
    parser.add_argument('--run', action='store_true', help='Make real model requests; may consume provider quota')
    args = parser.parse_args()
    city = next((city for city in CITIES if city['cityName'] == args.city), None)
    if city is None:
        parser.error('City must match a registered cityName')
    gemini_key = os.getenv('GEMINI_API_KEY', '').strip()
    gateway_key = os.getenv('FREELLMAPI_API_KEY', '').strip()
    gateway_base = os.getenv('FREELLMAPI_BASE_URL', 'http://127.0.0.1:3001/v1').strip()
    gateway_model = os.getenv('FREELLMAPI_MODEL', 'auto:fast').strip()
    gemini_model = os.getenv('GEMINI_ITINERARY_MODEL', '').strip() or os.getenv('GEMINI_MODEL', '').strip() or 'gemini-3.1-flash-lite'
    report = {'city': args.city, 'days': args.days, 'cached': False, 'comparison_complete': False,
              'providers': {'gemini': {'configured': bool(gemini_key), 'model': gemini_model},
                            'freellmapi': {'configured': bool(gateway_key), 'model': gateway_model}}}
    if not args.run:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    args.output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    context = await prepare_itinerary(plan_input(city, ItineraryRequest(cityName=args.city, budget=1000000, days=args.days)))
    report['context_seconds'] = round(time.monotonic() - started, 2)
    report['context_places'] = len(context['places'])
    (args.output / 'context.json').write_text(json.dumps(context, ensure_ascii=False, indent=2), encoding='utf-8')
    payload = json.dumps(context, ensure_ascii=False, separators=(',', ':'))
    instruction = quality_instruction(args.days)
    for provider, key in (('gemini', gemini_key), ('freellmapi', gateway_key)):
        result = report['providers'][provider]
        if not key:
            result.update(status='not_tested', reason='API key not configured')
            continue
        started = time.monotonic()
        try:
            if provider == 'gemini':
                level = thinking_level(gemini_model)
                if not level:
                    raise ValueError('Baseline supports the currently deployed Gemini 3 REST path only')
                raw = await _generate_fast(payload, instruction, gemini_model, key, level, args.days)
            else:
                raw, metadata = await candidate_request(gateway_base, key, gateway_model, payload, instruction, args.days)
                result.update(metadata)
            result['generation_seconds'] = round(time.monotonic() - started, 2)
            metrics, rendered = evaluate(raw, context)
            result.update(status='tested', **metrics)
            (args.output / f'{provider}-raw.json').write_text(raw, encoding='utf-8')
            if rendered:
                (args.output / f'{provider}-itinerary.txt').write_text(rendered, encoding='utf-8')
        except HTTPException as error:
            result.update(status='request_failed', http_status=error.status_code, reason=str(error.detail))
        except httpx.HTTPStatusError as error:
            result.update(status='request_failed', http_status=error.response.status_code)
        except (httpx.RequestError, ValueError, KeyError, IndexError, TypeError):
            result.update(status='request_failed', reason='Connection, configuration or response format error')
        result['total_request_seconds'] = round(time.monotonic() - started, 2)
        (args.output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'provider': provider, **result}, ensure_ascii=False), flush=True)
    report['comparison_complete'] = all(result.get('status') == 'tested' for result in report['providers'].values())
    report['human_quality_review_complete'] = False
    (args.output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'comparison_complete': report['comparison_complete'], 'report_saved': str(args.output / 'report.json')}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main())
