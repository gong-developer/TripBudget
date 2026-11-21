"""Bound public API traffic before paid services or local CPU work are invoked."""
import hashlib
import asyncio
import math
import os
import sqlite3
import threading
import time

from starlette.responses import JSONResponse
from .storage import database

FREE_PATHS = {'/api/health', '/api/countries', '/api/cities', '/api/trip-options'}


def setting(name, default):
    try:
        return max(1, int(os.getenv(name, default)))
    except ValueError:
        return default


def reserve(path, client, now):
    """Atomic fixed-window counters; trusted client IP comes from ASGI, not headers."""
    identity = hashlib.sha256(client.encode()).hexdigest()
    minute = math.floor(now / 60)
    day = math.floor(now / 86400)
    limits = [(f'client:{identity}:{minute}', setting('API_REQUESTS_PER_MINUTE', 60), (minute+1)*60)]
    if path == '/api/flights/search':
        limits.append((f'flight:{identity}:{minute}', setting('FLIGHT_REQUESTS_PER_MINUTE', 3), (minute+1)*60))
    if path == '/api/generate-itinerary':
        limits.append((f'ai:{identity}:{minute}', setting('AI_REQUESTS_PER_MINUTE', 5), (minute+1)*60))
    if path not in FREE_PATHS:
        limits.append((f'daily:{day}', setting('API_REQUESTS_PER_DAY', 2000), (day+1)*86400))
        if path == '/api/generate-itinerary':
            limits.append((f'ai-daily:{day}', setting('AI_REQUESTS_PER_DAY', 200), (day+1)*86400))
    with database('API_LIMIT_DB', 'api-limits.sqlite3') as db:
        db.execute('CREATE TABLE IF NOT EXISTS counters (key TEXT PRIMARY KEY, count INTEGER NOT NULL, expires REAL NOT NULL)')
        db.execute('BEGIN IMMEDIATE')
        db.execute('DELETE FROM counters WHERE expires <= ?', (now,))
        for key, maximum, expires in limits:
            row = db.execute('SELECT count FROM counters WHERE key=?', (key,)).fetchone()
            if row and row[0] >= maximum:
                return max(1, math.ceil(expires-now))
        for key, _, expires in limits:
            db.execute('INSERT INTO counters VALUES (?,1,?) ON CONFLICT(key) DO UPDATE SET count=count+1', (key, expires))
    return 0


class APIProtectionMiddleware:
    def __init__(self, app):
        self.app = app
        self.active = 0
        self.lock = threading.Lock()

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        async def secure_send(message):
            if message['type'] == 'http.response.start':
                message['headers'] = [*message.get('headers', []),
                    (b'x-content-type-options', b'nosniff'),
                    (b'referrer-policy', b'strict-origin-when-cross-origin'),
                    (b'x-frame-options', b'DENY')]
                if scope['path'].startswith('/api/') and scope['path'] not in FREE_PATHS:
                    message['headers'].append((b'cache-control', b'no-store'))
            await send(message)

        async def reject(status, detail, retry=None):
            response = JSONResponse({'detail': detail}, status_code=status,
                                    headers={'Retry-After': str(retry)} if retry else None)
            await response(scope, receive, secure_send)

        path = scope['path']
        if not path.startswith('/api/') or path == '/api/health' or scope['method'] == 'OPTIONS':
            return await self.app(scope, receive, secure_send)
        limit = setting('API_MAX_BODY_BYTES', 131072)
        body = bytearray()
        if scope['method'] in ('POST', 'PUT', 'PATCH'):
            length = dict(scope.get('headers', [])).get(b'content-length')
            if length is not None:
                try:
                    if int(length) > limit:
                        return await reject(413, '요청 내용이 너무 커요. 여행 계획의 크기를 줄여주세요.')
                except ValueError:
                    return await reject(400, '요청 형식이 올바르지 않아요.')
            try:
                async with asyncio.timeout(10):
                    while True:
                        message = await receive()
                        if message['type'] == 'http.disconnect':
                            return
                        body.extend(message.get('body', b''))
                        if len(body) > limit:
                            return await reject(413, '요청 내용이 너무 커요. 여행 계획의 크기를 줄여주세요.')
                        if not message.get('more_body', False):
                            break
            except TimeoutError:
                return await reject(408, '요청 전송이 지연되고 있어요. 연결을 확인하고 다시 시도해주세요.')
        try:
            retry = reserve(path, (scope.get('client') or ('unknown',))[0], time.time())
        except (sqlite3.Error, OSError):
            return await reject(503, '서버가 잠시 요청을 처리할 수 없어요. 잠시 후 다시 시도해주세요.', 10)
        if retry:
            wait = f'{math.ceil(retry/3600)}시간' if retry >= 3600 else f'{math.ceil(retry/60)}분' if retry >= 60 else f'{retry}초'
            return await reject(429, f'요청 한도에 도달했어요. 약 {wait} 후 다시 시도해주세요.', retry)
        with self.lock:
            accepted = self.active < setting('API_MAX_CONCURRENT', 8)
            if accepted:
                self.active += 1
        if not accepted:
            return await reject(503, '접속이 몰리고 있어요. 잠시 후 다시 시도해주세요.', 5)
        pending = scope['method'] in ('POST', 'PUT', 'PATCH')

        async def buffered_receive():
            nonlocal pending
            if pending:
                pending = False
                return {'type': 'http.request', 'body': bytes(body), 'more_body': False}
            return await receive()
        try:
            await self.app(scope, buffered_receive, secure_send)
        finally:
            with self.lock:
                self.active -= 1
