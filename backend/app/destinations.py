"""Server-side destination search; provider credentials never reach the browser."""
import math
import asyncio
import os
import random
from random import choice as choose_category
import httpx
from fastapi import HTTPException
from .place_names import korean_names, NAME_POLICY, REJECTED_NAMES
from .geoapify_destinations import overseas_candidates
from .countries import validate_country_filter, filter_country
from .travel_policy import EXCLUDED_COUNTRIES
from .destination_region import overseas_region
from .domestic_regions import domestic_candidates
from .overseas_regions import as_overseas_region


async def budget_candidates(category, country_code=None):
    """Compare live overseas cities and domestic administrative regions."""
    validate_country_filter(category, country_code)
    if country_code and country_code != 'kr':
        return await overseas_candidates(country_code=country_code)
    if category == 'international':
        return await overseas_candidates()
    if category == 'domestic' or country_code == 'kr':
        return await domestic_budget_candidates()
    overseas, domestic = await asyncio.gather(overseas_candidates(), domestic_budget_candidates())
    return domestic + overseas


async def domestic_budget_candidates():
    return domestic_candidates()


async def random_destination(category, country_code=None):
    validate_country_filter(category, country_code)
    chosen = ('domestic' if country_code == 'kr' else 'international') if country_code else (choose_category(["domestic", "international"]) if category == "all" else category)
    if chosen=='international':
        return random.choice(await overseas_candidates(batches=1,country_code=country_code)) if country_code else random.choice(await overseas_candidates(batches=1))
    return random.choice(domestic_candidates())


async def search_destinations(query, category):
    if category == 'domestic':
        return domestic_candidates(query)
    key_name = "GEOAPIFY_API_KEY"
    key = os.getenv(key_name, "").strip()
    if not key:
        raise HTTPException(503, f"여행지 검색을 사용하려면 backend/.env에 {key_name}를 설정해주세요.")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get("https://api.geoapify.com/v1/geocode/search", params={
                "apiKey": key, "text": query, "type": "city", "lang": "ko", "limit": 20, "format": "json",
            })
            response.raise_for_status()
            raw=[]
            originals={}
            for row in response.json().get('results',[])[:20]:
                if row.get('country_code','').lower() in ('kr','') or row.get('country_code','').lower() in EXCLUDED_COUNTRIES: continue
                if not (row.get('city') or row.get('name')): continue
                if (row.get('city') or row.get('name')) in REJECTED_NAMES:continue
                name,country,localized=await korean_names(client,row)
                try:
                    p_lat,p_lon=float(row.get('lat')),float(row.get('lon'))
                except (TypeError,ValueError):
                    continue
                raw.append((name,p_lat,p_lon,country))
                originals[(name,p_lat,p_lon)]=(str(row.get('city') or row.get('name')),row.get('country_code','').lower(),localized,overseas_region(row),row.get('place_id'))
            source = "Geoapify / OpenStreetMap"
        results = {}
        for name, lat, lng, region in raw:
            try:
                lat, lng = float(lat), float(lng)
                if not name or not math.isfinite(lat) or not math.isfinite(lng) or not (-90 <= lat <= 90 and -180 <= lng <= 180):
                    continue
                label = f"{name} · {region}" if region else name
                results[label] = {"cityName": label, "lat": lat, "lng": lng, "category": category,
                                  "estimatedCost": 1500000,
                                  "satisfaction": 75, "recommendedPlaces": [name], "source": source,
                                  "costIsEstimate": True, "regionName":''}
                if category=='international':
                    # Keep the provider original available for future policy changes.
                    details=originals.get((name,lat,lng))
                    if details:
                        results[label].update(originalName=details[0],countryCode=details[1],nameLocalized=details[2],displayName=label,namePolicy=NAME_POLICY,regionName=details[3],placeId=details[4])
                        results[label] = as_overseas_region(results[label])
            except (ValueError, TypeError):
                continue
        return filter_country(results.values(), None)
    except httpx.TimeoutException:
        raise HTTPException(504, "여행정보 API 응답이 지연되고 있어요. 다시 검색해주세요.") from None
    except httpx.HTTPStatusError as error:
        status = 429 if error.response.status_code == 429 else 502
        raise HTTPException(status, "여행정보 API 요청에 실패했어요. 인증키·활용신청·호출 한도를 확인해주세요.") from None
    except (httpx.RequestError, ValueError, KeyError, TypeError, AttributeError):
        raise HTTPException(502, "여행정보 API에 연결할 수 없거나 응답 형식이 올바르지 않아요.") from None
