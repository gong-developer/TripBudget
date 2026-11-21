import json
from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException
from .travel_policy import EXCLUDED_COUNTRIES, allowed_destination, require_country


@lru_cache(maxsize=1)
def country_boundaries():
    try:
        data = json.loads((Path(__file__).resolve().parents[1]/'data'/'countries.geojson').read_text(encoding='utf-8'))
        return {**data, 'features':[feature for feature in data['features'] if feature['properties']['code'] not in EXCLUDED_COUNTRIES]}
    except (OSError, ValueError):
        raise HTTPException(503, '국가 경계 데이터를 불러오지 못했어요. 서버 데이터를 확인해주세요.') from None


@lru_cache(maxsize=1)
def country_index():
    return {feature['properties']['code']:feature['properties'] for feature in country_boundaries()['features']}


def country_info(code):
    require_country(code)
    country = country_index().get(code)
    if country is None:
        raise HTTPException(422, '선택한 국가 코드를 확인해주세요. 국가 목록에서 다시 선택해주세요.')
    return country


def validate_country_filter(category, code):
    if not code:
        return
    country_info(code)
    if (code == 'kr' and category == 'international') or (code != 'kr' and category == 'domestic'):
        raise HTTPException(422, '선택한 국가와 국내·해외 지역 조건이 일치하지 않아요.')


def filter_country(cities, code):
    cities = [city for city in cities if allowed_destination(city)]
    if not code:
        return list(cities)
    return [city for city in cities if (city.get('countryCode') or
            ('kr' if city.get('category') == 'domestic' else '')).lower() == code]
