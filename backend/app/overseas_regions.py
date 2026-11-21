"""Overseas destinations select a city first, then sights inside that city."""
import hashlib
import re
from fastapi import HTTPException
from .sight_errors import NoSights
from .costs import distance
from .place_names import REJECTED_NAMES, normalized_name
from .travel_services import geo_request, coordinates, place_summary, localize_places


def as_overseas_region(city):
    identity = str(city.get('placeId') or f"{city['countryCode']}:{city.get('originalName') or city['cityName']}:{city['lat']:.5f}:{city['lng']:.5f}")
    name = (city.get('displayName') or city.get('originalName') or city['cityName']).split(' · ')[0]
    areas = [part.strip() for part in (city.get('regionName') or '').split(' · ') if part.strip()]
    return {**city, 'destinationType':'region', 'regionId':'geo:'+hashlib.sha256(identity.encode()).hexdigest()[:28],
            'regionName':' · '.join(dict.fromkeys([*areas,name]))[:200], 'recommendedPlaces':[]}


async def overseas_sights(city, limit=48):
    code = str(city.get('countryCode') or '').lower()
    if not re.fullmatch('[a-z]{2}', code) or code == 'kr':
        raise HTTPException(422, '해외 여행 지역을 다시 선택해주세요.')
    lat, lng = (city['location'] if 'location' in city else (city['lat'],city['lng']))
    name = city.get('originalName') or city.get('city') or city['cityName']
    name = name.split(' · ')[0]
    location = await geo_request('/v1/geocode/search', {
        'text':name, 'type':'city', 'filter':f'countrycode:{code}',
        'bias':f'proximity:{lng},{lat}', 'lang':'ko', 'format':'json', 'limit':3})
    rows = location.get('results')
    if not isinstance(rows, list):
        raise HTTPException(502, '해외 지역 API 응답 형식이 올바르지 않아요.')
    boundaries = []
    for row in rows:
        try:
            if str(row.get('country_code') or '').lower() != code or row.get('result_type') != 'city':
                continue
            r_lat, r_lng = coordinates({'properties':row})
            km = distance(lat,lng,r_lat,r_lng)
            identifier = row.get('place_id')
            if km <= 25 and isinstance(identifier, str) and identifier:
                boundaries.append((km,identifier,row))
        except (ValueError, TypeError, KeyError, AttributeError, IndexError):
            continue
    if not boundaries:
        raise NoSights(404, '선택한 해외 도시의 경계를 확인하지 못했어요. 다른 지역을 선택하거나 다시 시도해주세요.')
    _, boundary, area = min(boundaries,key=lambda item:item[0])
    result = await geo_request('/v2/places', {
        'categories':'tourism.sights,tourism.attraction', 'filter':f'place:{boundary}',
        'bias':f'proximity:{lng},{lat}', 'lang':'ko', 'limit':100})
    features = result.get('features')
    if not isinstance(features, list):
        raise HTTPException(502, '해외 지역 명소 API 응답 형식이 올바르지 않아요.')
    places = {}
    for feature in features[:100]:
        try:
            row = feature.get('properties') or {}
            if str(row.get('country_code') or '').lower() != code:
                continue
            if row.get('result_type') in ('city','country','state','county','district'):
                continue
            categories = row.get('categories')
            if isinstance(categories, list) and categories and not any(str(category).startswith(('tourism.sights','tourism.attraction')) for category in categories):
                continue
            # The provider boundary is primary; reject mismatching city IDs and
            # faraway or wrong-country records if a provider ignores its filter.
            if row.get('city_place_id') and row['city_place_id'] != boundary:
                continue
            place = place_summary(feature)
            if place['name'] in REJECTED_NAMES or place['originalName'] in REJECTED_NAMES or distance(lat,lng,place['lat'],place['lng']) > 30:
                continue
            bbox = area.get('bbox')
            if isinstance(bbox, dict) and all(key in bbox for key in ('lon1','lat1','lon2','lat2')):
                if not (bbox['lon1'] <= place['lng'] <= bbox['lon2'] and bbox['lat1'] <= place['lat'] <= bbox['lat2']):
                    continue
            identity = normalized_name(place['originalName'])
            if identity and identity not in places:
                places[identity] = place
        except (ValueError, TypeError, KeyError, AttributeError, IndexError):
            continue
    ordered = sorted(places.values(),key=lambda place:distance(lat,lng,place['lat'],place['lng']))[:limit]
    if not ordered:
        raise NoSights(503, '선택한 해외 지역에서 명소를 찾지 못했어요. 다른 지역을 선택하거나 다시 시도해주세요.')
    return {'places':await localize_places(ordered), 'source':'Geoapify / OpenStreetMap'}
