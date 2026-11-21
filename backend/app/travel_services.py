"""Bounded Geoapify lookups for sights, details and actual daily routes."""
import asyncio
import hashlib
import math
import os
import time
from collections import OrderedDict
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException
from .place_names import korean_only, normalized_name, NAME_POLICY, REJECTED_NAMES

CACHE = OrderedDict()
TTL = 600


async def geo_request(path, params):
    key = os.getenv('GEOAPIFY_API_KEY', '').strip()
    if not key:
        raise HTTPException(503, '명소·경로 조회를 사용하려면 GEOAPIFY_API_KEY를 설정해주세요.')
    cache_key = (hashlib.sha256(key.encode()).digest(), path, tuple(sorted(params.items())))
    now = time.monotonic()
    for expired, (expiry, _) in list(CACHE.items()):
        if expiry <= now:
            CACHE.pop(expired, None)
    if cache_key in CACHE:
        CACHE.move_to_end(cache_key)
        return CACHE[cache_key][1]
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.get('https://api.geoapify.com' + path, params={**params, 'apiKey':key})
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError('Invalid response')
        CACHE[cache_key] = (time.monotonic() + TTL, data)
        while len(CACHE) > 128:
            CACHE.popitem(last=False)
        return data
    except httpx.TimeoutException:
        raise HTTPException(504, '명소·경로 API 응답이 늦어지고 있어요. 다시 시도해주세요.') from None
    except httpx.HTTPStatusError as error:
        raise HTTPException(429 if error.response.status_code == 429 else 502,
                            '명소·경로 조회에 실패했어요. Geoapify 키·한도·접근 설정을 확인해주세요.') from None
    except (httpx.RequestError, ValueError, TypeError):
        raise HTTPException(502, '명소·경로 API 연결 또는 응답에 문제가 있어요.') from None


def coordinates(feature):
    row = feature.get('properties') or {}
    geometry = (feature.get('geometry') or {}).get('coordinates') or [None, None]
    lat, lon = float(row.get('lat', geometry[1])), float(row.get('lon', geometry[0]))
    if not math.isfinite(lat) or not math.isfinite(lon) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError('Invalid coordinates')
    return lat, lon


def safe_website(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = urlparse(value)
        return value if parsed.scheme in ('http', 'https') and parsed.netloc else None
    except ValueError:
        return None


def place_summary(feature):
    row = feature.get('properties') or {}
    lat, lon = coordinates(feature)
    translations = row.get('name_international') or {}
    if not isinstance(translations, dict):
        translations = {}
    datasource=row.get('datasource') or {}
    raw=(datasource.get('raw') or {}) if isinstance(datasource,dict) else {}
    if not isinstance(raw,dict):raw={}
    original = str(raw.get('name') or row.get('name') or row.get('address_line1') or '이름 미제공')[:200]
    if original in REJECTED_NAMES:
        original=str(translations.get('en') or '이름 미제공')[:200]
    korean=next((value for value in (translations.get('ko'),raw.get('name:ko'),row.get('name')) if korean_only(value)),None)
    name = korean or original
    english = translations.get('en')
    return {'name':name, 'originalName':original, 'namePolicy':NAME_POLICY, 'nameSource':'provider' if korean else 'original',
            'englishName':english[:200] if isinstance(english, str) else None, 'lat':lat, 'lng':lon,
            'placeId':row.get('place_id'), 'address':str(row.get('formatted') or '')[:600],
            'openingHours':row.get('opening_hours') if isinstance(row.get('opening_hours'), str) else None,
            'website':safe_website(row.get('website')), 'source':'Geoapify / OpenStreetMap'}


async def localize_places(places):
    result=[]
    for place in places:
        original=place.get('originalName') or (place.get('name') if not place.get('nameTranslated') else None) or '명소 이름 재조회 필요'
        if original in REJECTED_NAMES:
            original=place.get('englishName') or '명소 이름 재조회 필요'
        trusted=place.get('namePolicy')==NAME_POLICY and not place.get('nameTranslated')
        name=place['name'] if trusted and korean_only(place.get('name')) else original
        result.append({**place,'name':name,'originalName':original,'nameTranslated':False,'namePolicy':NAME_POLICY})
    return result


async def nearby_places(city):
    if city.get('destinationType') == 'region' and city.get('category') == 'international':
        from .overseas_regions import overseas_sights
        return await overseas_sights(city, limit=12)
    if city.get('destinationType') == 'region' and city.get('category') == 'domestic':
        from .domestic_sights import domestic_sights
        return await domestic_sights(city, limit=12)
    data = await geo_request('/v2/places', {'categories':'tourism.sights,tourism.attraction',
        'filter':f"circle:{city['lng']},{city['lat']},15000",
        'bias':f"proximity:{city['lng']},{city['lat']}", 'lang':'ko', 'limit':12})
    places = {}
    features = data.get('features')
    if not isinstance(features, list):
        raise HTTPException(502, '주변 명소 API 응답 형식이 올바르지 않아요.')
    for feature in features[:12]:
        try:
            item = place_summary(feature)
            places[(item['name'], item['lat'], item['lng'])] = item
        except (ValueError, TypeError, KeyError, IndexError, AttributeError):
            continue
    return {'places':await localize_places(list(places.values())), 'source':'Geoapify / OpenStreetMap'}


async def place_details(place_id, lat, lng):
    params = {'id':place_id} if place_id else {'lat':lat, 'lon':lng}
    data = await geo_request('/v2/place-details', {**params, 'features':'details', 'lang':'ko'})
    try:
        item = place_summary(data['features'][0])
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        raise HTTPException(404, '이 장소의 상세 정보를 찾지 못했어요.') from None
    return (await localize_places([item]))[0]


async def daily_route(city, names, mode):
    names = list(dict.fromkeys(name.strip() for name in names if name.strip()))
    if len(names) < 2:
        raise HTTPException(422, '경로를 표시하려면 서로 다른 명소가 두 곳 이상 필요해요.')
    nearby = await nearby_places(city)

    async def resolve(name):
        known = [place for place in nearby['places'] if normalized_name(name) in
                 {normalized_name(place['name']), normalized_name(place['originalName']),
                  normalized_name(place.get('englishName') or '')}]
        if len(known) == 1:
            return {key:known[0][key] for key in ('name','lat','lng','placeId')}
        data = await geo_request('/v1/geocode/search', {
            'text':f"{name}, {city['cityName'].replace(' · ', ', ')}", 'lang':'ko', 'format':'json', 'limit':3,
            'filter':f"circle:{city['lng']},{city['lat']},50000",
            'bias':f"proximity:{city['lng']},{city['lat']}"})
        rows = data.get('results')
        if not isinstance(rows, list):
            raise HTTPException(502, '명소 위치 API 응답 형식이 올바르지 않아요.')
        for row in rows[:3]:
            if not isinstance(row, dict) or row.get('result_type') in ('city','country','state','county','district'):
                continue
            try:
                lat, lon = coordinates({'properties':row})
                # Reject distant or cross-country matches even if the provider ignores a filter.
                distance = math.hypot(lat-city['lat'], (lon-city['lng'])*math.cos(math.radians(city['lat'])))
                code = str(row.get('country_code') or '').lower()
                if distance > .45 or (city.get('countryCode') and code and code != city['countryCode'].lower()):
                    continue
                if (row.get('rank') or {}).get('confidence', 1) < .6:
                    continue
                return {'name':name, 'lat':lat, 'lng':lon, 'placeId':row.get('place_id')}
            except (ValueError, TypeError, IndexError, AttributeError):
                continue
        raise HTTPException(404, f'일정의 명소 위치를 확인하지 못했어요: {name}. 다른 날짜를 선택하거나 주변 명소를 확인해주세요.')

    points = await asyncio.gather(*(resolve(name) for name in names))
    if len({(point['lat'], point['lng']) for point in points}) < 2:
        raise HTTPException(404, '명소들이 같은 위치로 조회되어 실제 이동 경로를 표시할 수 없어요.')
    data = await geo_request('/v1/routing', {
        'waypoints':'|'.join(f"{point['lat']},{point['lng']}" for point in points),
        'mode':mode, 'format':'geojson'})
    try:
        feature = data['features'][0]
        geometry = feature['geometry']
        raw_lines = geometry['coordinates'] if geometry['type'] == 'MultiLineString' else [geometry['coordinates']]
        if geometry['type'] not in ('MultiLineString','LineString'):
            raise ValueError('Not a route')
        lines = []
        for line in raw_lines:
            if len(line) < 2:
                continue
            lines.append([list(coordinates({'geometry':{'coordinates':point}})) for point in line])
        if not lines:
            raise ValueError('No route geometry')
        properties = feature['properties']
        distance, duration = float(properties['distance']), float(properties['time'])
        if not all(math.isfinite(value) and value >= 0 for value in (distance, duration)) or distance == 0:
            raise ValueError('Invalid totals')
        return {'lines':lines, 'waypoints':points, 'distance':distance, 'duration':duration,
                'mode':mode, 'source':'Geoapify Routing'}
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        raise HTTPException(404, '이 명소들을 연결하는 실제 이동 경로를 찾지 못했어요.') from None
