"""Only recommend regions whose provider sights have actually been verified."""
import asyncio
from collections import OrderedDict, defaultdict
import hashlib
import math
import os
import random
import time

import httpx
from fastapi import HTTPException
from .place_names import REJECTED_NAMES, normalized_name
from .sight_errors import NoSights
from .itinerary_context import prepare_itinerary, minimum_sights, usable_name
from .costs import TripOptions
from .compact_itinerary import plan_input

CACHE = OrderedDict()
INFLIGHT = {}
CANDIDATE_LIMIT = 24


async def fetch_nearby(city, days):
    # Reuse the itinerary's full provider lookup, radius and name deduplication.
    # This only prepares grounded places; it never calls Gemini.
    return await prepare_itinerary(plan_input(city, TripOptions(days=days)), require_sufficient=False)


def cache_key(city, days=3):
    credential = '\0'.join(os.getenv(name,'') for name in ('TOUR_API_KEY','GEOAPIFY_API_KEY'))
    return (city['cityName'],city['lat'],city['lng'],city.get('regionId'),days,
            hashlib.sha256(credential.encode()).digest())


def cached_sights(city, days=3):
    key=cache_key(city,days)
    if key in CACHE:
        expiry,data=CACHE[key]
        if expiry>time.monotonic():
            CACHE.move_to_end(key)
            return data
        CACHE.pop(key,None)
    return None


def valid_sight(place):
    try:
        name=place.get('name')
        lat,lng=float(place['lat']),float(place['lng'])
        return (isinstance(name,str) and bool(name.strip()) and name not in REJECTED_NAMES
                and math.isfinite(lat) and math.isfinite(lng) and -90<=lat<=90 and -180<=lng<=180)
    except (ValueError,TypeError,KeyError,AttributeError):
        return False


async def confirmed_nearby(city, days=3):
    cached=cached_sights(city,days)
    if cached is not None:
        return cached
    key=cache_key(city,days)
    task=INFLIGHT.get(key)
    if task is None:
        async def fetch():
            try:
                data=await asyncio.wait_for(fetch_nearby(city,days),timeout=12)
                if not isinstance(data,dict) or not isinstance(data.get('places'),list):
                    raise HTTPException(502,'명소 API 응답 형식이 올바르지 않아요.')
                seen=set()
                unique=[]
                for place in data['places']:
                    if not valid_sight(place) or not usable_name(place['name']):
                        continue
                    original=place.get('originalName') or place['name']
                    if not usable_name(original):
                        continue
                    identity=normalized_name(original)
                    if identity in seen:
                        continue
                    seen.add(identity);unique.append(place)
                data={**data,'places':unique}
            except NoSights:
                data={'places':[]}
            # Connection/authentication/timeout failures are deliberately not
            # cached as "no sights": a later healthy request may verify this city.
            CACHE[key]=(time.monotonic()+(600 if data['places'] else 180),data)
            CACHE.move_to_end(key)
            while len(CACHE)>256:
                CACHE.popitem(last=False)
            return data
        task=asyncio.create_task(fetch())
        INFLIGHT[key]=task
        def finished(done):
            if INFLIGHT.get(key) is done:
                INFLIGHT.pop(key,None)
            if not done.cancelled():
                done.exception()
        task.add_done_callback(finished)
    return await asyncio.shield(task)


def candidate_pool(cities,limit,days=3):
    unique={city['cityName']:city for city in cities}
    eligible=[]
    for city in unique.values():
        cached=cached_sights(city,days)
        if cached is None or len(cached['places'])>=minimum_sights(days):
            eligible.append(city)
    if len(eligible)<=limit:
        return eligible
    groups=defaultdict(list)
    for city in eligible:
        cost=city.get('costBreakdown',{}).get('high',city.get('estimatedCost',0))
        groups[(city.get('category',''),int(cost)//500000)].append(city)
    buckets=[]
    for key in sorted(groups,key=lambda key:(-key[1],key[0])):
        bucket=groups[key]
        random.shuffle(bucket)
        bucket.sort(key=lambda city:cached_sights(city,days) is None)
        buckets.append(bucket)
    result=[]
    while len(result)<limit and any(buckets):
        for bucket in buckets:
            if bucket and len(result)<limit:
                result.append(bucket.pop(0))
    return result


async def confirmed_destinations(cities,*,days=3,limit=CANDIDATE_LIMIT,timeout=15):
    pool=candidate_pool(cities,limit,days)
    if not pool:
        return []
    gate=asyncio.Semaphore(4)
    errors=[]
    async def verify(city):
        async with gate:
            try:
                nearby=await confirmed_nearby(city,days)
                if len(nearby['places'])>=minimum_sights(days):
                    return {**city,'sightCount':len(nearby['places']),'sightsVerified':True}
            except HTTPException as error:
                errors.append(error)
            except (TimeoutError,httpx.HTTPError):
                errors.append(HTTPException(503,'명소 조회를 완료하지 못했어요. 잠시 후 다시 시도해주세요.'))
            return None
    tasks=[asyncio.create_task(verify(city)) for city in pool]
    try:
        done,pending=await asyncio.wait(tasks,timeout=timeout)
        verified=[task.result() for task in tasks if task in done and task.result() is not None]
        if verified:
            return sorted(verified,key=lambda city:city.get('costBreakdown',{}).get('high',city.get('estimatedCost',0)))
        if pending:
            raise HTTPException(504,'명소 확인 시간이 초과됐어요. 국가나 여행 조건을 바꿔 다시 시도해주세요.')
        if errors:
            raise errors[0]
        return []
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
