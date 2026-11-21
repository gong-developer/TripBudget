"""Resolve sights inside the selected domestic region only when needed."""
from collections import OrderedDict
import hashlib
import math
import os
import time
from urllib.parse import unquote
import httpx
from fastapi import HTTPException
from .sight_errors import NoSights
from .domestic_regions import region_catalog
from .place_names import NAME_POLICY, REJECTED_NAMES

CACHE = OrderedDict()


async def domestic_sights(city, limit=48):
    region = next((row for row in region_catalog() if row['regionId'] == city.get('regionId')), None)
    if region is None:
        raise HTTPException(422, '국내 지역을 다시 선택해주세요.')
    key = unquote(os.getenv('TOUR_API_KEY', '').strip())
    if not key:
        raise HTTPException(503, '국내 명소·일정 조회를 사용하려면 TOUR_API_KEY를 설정해주세요.')
    cache_key = (hashlib.sha256(key.encode()).digest(), region['regionId'], limit)
    now = time.monotonic()
    for old_key, (expiry, _) in list(CACHE.items()):
        if expiry <= now:
            CACHE.pop(old_key, None)
    if cache_key in CACHE:
        return {'places':[dict(place) for place in CACHE[cache_key][1]], 'source':'한국관광공사 TourAPI'}
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            async def request(path, params):
                response = await client.get('https://apis.data.go.kr/B551011/KorService2/' + path, params={
                    'serviceKey':key, 'MobileOS':'ETC', 'MobileApp':'TripBudget', '_type':'json',
                    'numOfRows':100, 'pageNo':1, **params})
                response.raise_for_status()
                envelope = response.json()['response']
                if str(envelope['header']['resultCode']) != '0000':
                    raise HTTPException(502, 'TourAPI 명소 조회가 거부됐어요. 활용신청·키·한도를 확인해주세요.')
                rows = (envelope['body'].get('items') or {}).get('item') or []
                return [rows] if isinstance(rows, dict) else rows

            params = {'areaCode':region['areaCode'], 'contentTypeId':'12', 'arrange':'Q'}
            if region['districtName']:
                districts = await request('areaCode2', {'areaCode':region['areaCode']})
                code = next((str(row['code']) for row in districts
                             if row.get('name') == region['districtName'] and row.get('code') is not None), None)
                if code is None:
                    raise NoSights(404, '선택한 지역의 TourAPI 코드를 찾지 못했어요. 다른 지역을 선택해주세요.')
                params['sigunguCode'] = code
            rows = await request('areaBasedList2', params)
        places = []
        seen = set()
        for row in rows:
            try:
                name = row.get('title')
                lat, lng = float(row.get('mapy')), float(row.get('mapx'))
                if not isinstance(name, str) or not name.strip() or name in REJECTED_NAMES or not all(map(math.isfinite, (lat,lng))) or not (32 <= lat <= 39.5 and 124 <= lng <= 132):
                    continue
                # Reject other administrative areas even if a provider ignores its filter.
                if row.get('areacode') and str(row['areacode']) != region['areaCode']:
                    continue
                if params.get('sigunguCode') and row.get('sigungucode') and str(row['sigungucode']) != params['sigunguCode']:
                    continue
                identity = (name, lat, lng)
                if identity in seen:
                    continue
                seen.add(identity)
                places.append({'name':name.strip(), 'originalName':name.strip(), 'lat':lat, 'lng':lng,
                               'placeId':None, 'contentId':str(row.get('contentid') or ''),
                               'address':' '.join(str(row.get(field) or '').strip() for field in ('addr1','addr2')).strip(),
                               'namePolicy':NAME_POLICY, 'nameTranslated':False,
                               'source':'한국관광공사 TourAPI'})
            except (ValueError, TypeError, AttributeError):
                continue
        places = sorted(places, key=lambda place: (place['lat']-region['lat'])**2 + (place['lng']-region['lng'])**2)[:limit]
        if not places:
            raise NoSights(503, '선택한 지역에서 유효한 명소를 찾지 못했어요. 다른 지역을 선택하거나 다시 시도해주세요.')
        CACHE[cache_key] = (time.monotonic()+600, places)
        while len(CACHE) > 64:
            CACHE.popitem(last=False)
        return {'places':[dict(place) for place in places], 'source':'한국관광공사 TourAPI'}
    except httpx.TimeoutException:
        raise HTTPException(504, '국내 명소 API 응답이 늦어지고 있어요. 다시 시도해주세요.') from None
    except httpx.HTTPStatusError as error:
        raise HTTPException(429 if error.response.status_code == 429 else 502, '국내 명소 조회에 실패했어요. TourAPI 키·한도를 확인해주세요.') from None
    except (httpx.RequestError, ValueError, KeyError, TypeError, AttributeError):
        raise HTTPException(502, '국내 명소 API 연결 또는 응답 형식에 문제가 있어요.') from None
