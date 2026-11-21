"""Domestic destinations are administrative regions; sights are chosen later."""
from functools import lru_cache
import json
from pathlib import Path
from fastapi import HTTPException


@lru_cache(maxsize=1)
def region_catalog():
    try:
        rows = json.loads((Path(__file__).resolve().parents[1] / 'data' / 'domestic_regions.json').read_text(encoding='utf-8'))['regions']
        if not rows:
            raise ValueError('Empty regions')
        return rows
    except (OSError, ValueError, KeyError):
        raise HTTPException(503, '국내 지역 목록을 불러오지 못했어요. 서버 데이터를 확인해주세요.') from None


def domestic_candidates(query=''):
    cities = []
    for region in region_catalog():
        area = ' · '.join(dict.fromkeys([region['province'], region['name']]))
        if query and query.strip() not in area.replace(' · ', ' '):
            continue
        label = f"{region['name']} · {region['province']}" if region['districtName'] else f"{region['name']} · 대한민국"
        cities.append({'cityName':label, 'displayName':label, 'originalName':region['name'],
                       'lat':region['lat'], 'lng':region['lng'], 'category':'domestic', 'countryCode':'kr',
                       'regionId':region['regionId'], 'destinationType':'region', 'regionName':area,
                       'areaCode':region['areaCode'], 'districtName':region['districtName'],
                       'recommendedPlaces':[], 'satisfaction':75, 'costIsEstimate':True,
                       'namePolicy':'registered-v1', 'nameLocalized':True, 'source':'GeoNames 국내 행정지역'})
    return cities


def region_history(cities):
    # Old attraction results remain restorable, but are no longer region candidates.
    from .overseas_regions import as_overseas_region
    results = []
    for city in cities:
        if city.get('destinationType') == 'region':
            results.append(city)
        elif city['category'] == 'international' and city.get('countryCode') and not city.get('destinationType'):
            results.append(as_overseas_region(city))
    return results
