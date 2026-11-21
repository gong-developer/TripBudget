"""Ground itineraries in provider places, retaining curated names as a fallback."""
import asyncio
from fastapi import HTTPException
from .place_names import normalized_name, REJECTED_NAMES
from .travel_services import geo_request, place_summary, localize_places, coordinates
from .costs import distance

BAD_NAMES = {normalized_name(name) for name in (*REJECTED_NAMES,'전체보기','더보기','홈','home','homepage','menu','full menu','undefined','null')}


def usable_name(name):
    return isinstance(name,str) and bool(name.strip()) and not any(char in name for char in ('\n','\r','|')) and normalized_name(name) not in BAD_NAMES


def minimum_sights(days):
    return days * 2


async def prepare_itinerary(data, *, require_sufficient=True):
    lat, lng = data['location']
    notes = []
    known = []
    try:
        async def fetch():
            if data.get('destinationType') == 'region' and data.get('countryCode') != 'kr':
                from .overseas_regions import overseas_sights
                result = await overseas_sights(data, limit=48)
                return [place for place in result['places'] if usable_name(place['name'])]
            if data.get('regionId') and data.get('countryCode') == 'kr':
                from .domestic_sights import domestic_sights
                result = await domestic_sights(data, limit=48)
                return [place for place in result['places'] if usable_name(place['name']) and distance(lat,lng,place['lat'],place['lng']) <= 32]
            result = await geo_request('/v2/places', {
                'categories': 'tourism.sights,tourism.attraction',
                'filter': f'circle:{lng},{lat},30000',
                'bias': f'proximity:{lng},{lat}', 'lang': 'ko',
                'limit': min(48, max(18, data['days'] * 4)),
            })
            if not isinstance(result.get('features'), list):
                raise HTTPException(502, '명소 목록 형식이 올바르지 않아요.')
            places = []
            for feature in result['features'][:48]:
                try:
                    code=str((feature.get('properties') or {}).get('country_code') or '').lower()
                    if code and data.get('countryCode') and code!=data['countryCode']:
                        continue
                    place = place_summary(feature)
                    if not usable_name(place['name']) or not usable_name(place['originalName']) or distance(lat,lng,place['lat'],place['lng']) > 32:
                        continue
                    place['categories']=(feature.get('properties') or {}).get('categories') or []
                    places.append(place)
                except (ValueError, TypeError, KeyError, IndexError, AttributeError):
                    continue
            return await localize_places(places)
        known = await asyncio.wait_for(fetch(), timeout=18 if data.get('destinationType') == 'region' else 10)
    except (HTTPException, asyncio.TimeoutError):
        if data.get('regionId') or data.get('destinationType') == 'region':
            raise
        notes.append('주변 명소 조회를 완료하지 못해 등록된 추천 명소만 사용했습니다.')

    sources = []
    seen = set()
    # Prioritize app-curated highlights when they match provider data. Unlike
    # nearby points, an unlocated curated name cannot justify a travel-time claim.
    city_name = normalized_name(data['city'].split(' · ')[0])
    curated=[] if data.get('destinationType') == 'region' else [name for name in data['places'] if usable_name(name) and normalized_name(name)!=city_name][:3]
    async def resolve_curated(name):
        match = next((p for p in known if normalized_name(name) in
                      {normalized_name(p['name']),normalized_name(p['originalName'])}), None)
        if match:
            return {**match,'priority':True}
        fallback={'name':name,'originalName':name,'lat':None,'lng':None,'source':'등록 추천 명소','priority':True}
        try:
            result=await geo_request('/v1/geocode/search',{
                'text':f"{name}, {data['city'].replace(' · ', ', ')}",'lang':'ko','format':'json','limit':3,
                'filter':f'circle:{lng},{lat},30000','bias':f'proximity:{lng},{lat}'})
            for row in result.get('results',[])[:3]:
                if row.get('result_type') in ('city','country','state','county','district','postcode') or (row.get('rank') or {}).get('confidence',0)<.6:
                    continue
                p_lat,p_lng=coordinates({'properties':row})
                code=str(row.get('country_code') or '').lower()
                if distance(lat,lng,p_lat,p_lng)>32 or (code and data.get('countryCode') and code!=data['countryCode']):
                    continue
                return {**fallback,'lat':p_lat,'lng':p_lng,'source':'Geoapify 검색'}
        except (HTTPException,ValueError,TypeError,KeyError,AttributeError,IndexError):
            pass
        return fallback
    if curated:
        tasks=[asyncio.create_task(resolve_curated(name)) for name in curated]
        try:
            sources.extend(await asyncio.wait_for(asyncio.gather(*tasks),timeout=4))
        except asyncio.TimeoutError:
            sources.extend({'name':name,'originalName':name,'lat':None,'lng':None,'source':'등록 추천 명소','priority':True} for name in curated)
    sources.extend(known)
    unique = []
    for place in sources:
        key = normalized_name(place['originalName'])
        if key in seen:
            continue
        seen.add(key)
        maximum=45 if any(word in place['name'] for word in ('동상','기념비','비석')) else 180
        unique.append({'name':place['name'], 'originalName':place['originalName'],
                       'lat':round(place['lat'],5) if place['lat'] is not None else None,
                       'lng':round(place['lng'],5) if place['lng'] is not None else None,
                       'openingHours':place.get('openingHours'), 'source':place.get('source'),
                       'priority':place.get('priority',False),'maxStayMinutes':maximum})
    unique = unique[:48]
    if require_sufficient and len(unique) < minimum_sights(data['days']):
        raise HTTPException(503, f"확인된 명소가 {len(unique)}곳이라 중복 없이 {data['days']}일 일정을 만들기 어려워요. 기간을 줄이거나 잠시 후 다시 시도해주세요.")
    if any(place['lat'] is None for place in unique):
        notes.append('일부 등록 명소는 좌표가 없어 이동 거리와 시간을 확인하지 못했습니다.')
    notes.append('명소 이름·위치를 바탕으로 구성한 제안입니다. 운영시간·휴무·예약 가능 여부는 방문 전에 확인해주세요.')
    return {**data,'places':unique,'contextNotes':notes}
