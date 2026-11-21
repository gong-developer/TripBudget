"""Live overseas city candidates; bounded calls, no catalog substitution."""
import asyncio
import math
import os
import random
import time
import hashlib

REGION_CACHE = {}
REGION_TTL = 300

import httpx
from fastapi import HTTPException
from .place_names import local_names, REJECTED_NAMES
from .countries import country_info
from .travel_policy import EXCLUDED_COUNTRIES
from .destination_region import overseas_region
from .travel_services import geo_request
from .overseas_regions import as_overseas_region

# Broad inhabited regions, not a fixed list of destination names.
REGIONS = (
    (100, 20, 146, 46), (94, -11, 142, 22), (60, 5, 100, 38),
    (26, 12, 60, 44), (-12, 35, 27, 60), (27, 44, 80, 65),
    (-18, 0, 40, 35), (10, -35, 51, 0), (-130, 25, -60, 60),
    (-110, 7, -60, 25), (-82, -55, -34, 7), (112, -47, 179, -10),
)


def parse_city(feature):
    row = feature.get('properties') or {}
    code = str(row.get('country_code') or '').lower()
    name = str(row.get('name') or row.get('city') or '').strip()
    country = str(row.get('country') or '').strip()
    if len(code) != 2 or not code.isalpha() or code == 'kr' or code in EXCLUDED_COUNTRIES or not name or not country or name in REJECTED_NAMES:
        return None
    coordinates = (feature.get('geometry') or {}).get('coordinates') or [None, None]
    lat, lon = float(row.get('lat', coordinates[1])), float(row.get('lon', coordinates[0]))
    if not math.isfinite(lat) or not math.isfinite(lon) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    city = {'cityName':f'{name} · {country}', 'lat':lat, 'lng':lon,
            'category':'international', 'countryCode':code, 'satisfaction':75,
            'recommendedPlaces':[], 'costIsEstimate':True, 'originalName':name,
            'placeId':row.get('place_id'), 'source':'Geoapify / OpenStreetMap',
            'regionName':overseas_region(row)}
    international = row.get('name_international')
    if isinstance(international, dict) and isinstance(international.get('en'), str):
        city['englishName'] = international['en'][:200]
    korean_name, korean_country = local_names({'city':name, 'country':country,
                                              'country_code':code, 'lat':lat, 'lon':lon})
    if korean_name and korean_country:
        city.update(displayName=f'{korean_name} · {korean_country}', nameLocalized=True)
    return as_overseas_region(city)


async def overseas_candidates(*, batches=4, country_code=None):
    key = os.getenv('GEOAPIFY_API_KEY', '').strip()
    if not key:
        raise HTTPException(503, '해외 추천을 사용하려면 backend/.env에 GEOAPIFY_API_KEY를 설정해주세요.')
    if country_code:
        country = country_info(country_code)
        if country_code == 'kr':
            raise HTTPException(422, '대한민국은 국내 여행지 조회를 사용해주세요.')
        location = await geo_request('/v1/geocode/search', {
            'text':country['englishName'], 'type':'country', 'filter':f'countrycode:{country_code}',
            'lang':'ko', 'limit':1, 'format':'json'})
        rows = location.get('results')
        identifier = next((row.get('place_id') for row in rows if isinstance(row, dict) and
                           str(row.get('country_code') or '').lower() == country_code), None) if isinstance(rows, list) else None
        if not isinstance(identifier, str) or not identifier:
            raise HTTPException(404, '선택한 국가의 API 경계를 찾지 못했어요. 다른 국가를 선택하거나 다시 시도해주세요.')
        regions = [f'place:{identifier}']
        limit = 120
    else:
        regions = ['rect:' + ','.join(map(str, bounds)) for bounds in random.sample(REGIONS, min(batches, len(REGIONS)))]
        limit = 40
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            async def fetch(spatial_filter):
                cache_key = (hashlib.sha256(key.encode()).digest(), spatial_filter, limit)
                now = time.monotonic()
                for expired_key, (expiry, _) in list(REGION_CACHE.items()):
                    if expiry <= now:
                        REGION_CACHE.pop(expired_key, None)
                cached = REGION_CACHE.get(cache_key)
                if cached:
                    return cached[1]
                response = await client.get('https://api.geoapify.com/v2/places', params={
                    'apiKey':key, 'categories':'populated_place.city',
                    'filter':spatial_filter, 'lang':'ko', 'limit':limit,
                })
                response.raise_for_status()
                features = response.json()['features']
                if not isinstance(features, list):
                    raise ValueError('Invalid features')
                if features:
                    REGION_CACHE[cache_key] = (time.monotonic() + REGION_TTL, features[:limit])
                    while len(REGION_CACHE) > 64:
                        REGION_CACHE.pop(next(iter(REGION_CACHE)))
                return features[:limit]
            results = await asyncio.gather(*(fetch(bounds) for bounds in regions))
        cities = {}
        for features in results:
            for feature in features:
                try:
                    city = parse_city(feature)
                    if city and (not country_code or city['countryCode'] == country_code):
                        cities[city['cityName']] = city
                except (ValueError, TypeError, IndexError, AttributeError):
                    continue
        if not cities:
            raise HTTPException(503, 'Geoapify에서 유효한 해외 도시를 찾지 못했어요. 다시 시도해주세요.')
        return list(cities.values())
    except httpx.TimeoutException:
        raise HTTPException(504, 'Geoapify 도시 조회 시간이 초과됐어요. 다시 시도해주세요.') from None
    except httpx.HTTPStatusError as error:
        raise HTTPException(429 if error.response.status_code == 429 else 502,
                            'Geoapify 도시 조회에 실패했어요. API 키·사용 한도·접근 설정을 확인해주세요.') from None
    except (httpx.RequestError, ValueError, KeyError, TypeError, AttributeError):
        raise HTTPException(502, 'Geoapify 연결 또는 응답 형식에 문제가 있어요. 다시 시도해주세요.') from None
