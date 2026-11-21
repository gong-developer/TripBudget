import asyncio
import json
from typing import Annotated, Literal

from fastapi import HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ConfigDict

from .budget_recommendation import choose_budget_destinations
from .costs import TripOptions, priced_city
from .destinations import budget_candidates
from .place_names import localize_destination_label, korean_only
from .travel_services import nearby_places, place_details, daily_route
from .countries import country_boundaries, validate_country_filter, filter_country
from .travel_policy import require_destination
from .destination_sights import confirmed_destinations
from .domestic_regions import region_history
from .overseas_regions import as_overseas_region
from .flight_quotes import FlightSearchRequest, airport_options, quote_for, quoted_cost


class ComparisonRequest(TripOptions):
    model_config = ConfigDict(extra='forbid')
    budget: int = Field(gt=0, le=100_000_000, strict=True)
    category: Literal['all','domestic','international'] = 'all'
    countryCode: str | None = Field(default=None,pattern='^[a-z]{2}$')


class SavedDestination(BaseModel):
    cityName: str = Field(min_length=1, max_length=200)
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lng: float = Field(ge=-180, le=180, allow_inf_nan=False)
    category: Literal['domestic','international']
    countryCode: str = Field(default='', max_length=2)
    regionName: str = Field(default='', max_length=200)
    regionId: str | None = Field(default=None, max_length=32)
    destinationType: Literal['region'] | None = None
    displayName: str | None = Field(default=None, max_length=200)
    originalName: str | None = Field(default=None, max_length=200)
    englishName: str | None = Field(default=None, max_length=200)
    placeId: str | None = Field(default=None, max_length=1024)
    recommendedPlaces: list[Annotated[str, Field(min_length=1,max_length=200)]] = Field(default_factory=list, max_length=24)
    nameTranslationNotice: str | None = Field(default=None, max_length=200)


class RestoreRequest(TripOptions):
    cities: list[SavedDestination] = Field(min_length=1, max_length=3)


class NearbyRequest(BaseModel):
    cityName: str = Field(min_length=1, max_length=200)


class PlaceDetailsRequest(BaseModel):
    placeId: str | None = Field(default=None, max_length=1024)
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lng: float = Field(ge=-180, le=180, allow_inf_nan=False)


class DayRouteRequest(NearbyRequest):
    placeNames: list[Annotated[str, Field(min_length=1,max_length=200)]] = Field(min_length=2, max_length=3)
    mode: Literal['walk','drive'] = 'walk'


def install_travel_features(app, registry, base_cities):
    @app.get('/api/countries')
    def countries():
        return JSONResponse(country_boundaries(),headers={'Cache-Control':'no-cache'})

    def remember(city):
        registry[city['cityName']] = city
        registry.move_to_end(city['cityName'])
        while len(registry) > 1000:
            registry.popitem(last=False)

    def find_city(name):
        city = registry.get(name) or next((c for c in base_cities if c['cityName'] == name), None)
        if city is None:
            raise HTTPException(404, '여행지를 다시 조회하거나 저장한 계획을 불러와주세요.')
        require_destination(city)
        return city

    @app.get('/api/flights/options')
    def flight_options(cityName: str = Query(min_length=1,max_length=200), origin: str = 'seoul'):
        from .costs import ORIGINS
        if origin not in ORIGINS:raise HTTPException(422,'출발 지역을 확인해주세요.')
        return airport_options(find_city(cityName),origin)

    @app.post('/api/flights/search')
    async def flight_search(request: FlightSearchRequest):
        city=find_city(request.cityName)
        quote=await quote_for(city,request)
        return {'quote':quote,'costBreakdown':quoted_cost(city,request,quote)}

    @app.get('/api/destination-photo', tags=['여행지 조회'], summary='선택 지역 사진 조회')
    async def photo(cityName: str = Query(min_length=1, max_length=200)):
        from .destination_photos import destination_photo
        return {'photo':await destination_photo(find_city(cityName))}

    @app.post('/api/destinations/compare', response_class=StreamingResponse)
    async def compare_destinations(request: ComparisonRequest):
        validate_country_filter(request.category, request.countryCode)
        def event(kind, **values):
            return json.dumps({'type':kind, **values}, ensure_ascii=False) + '\n'

        async def stream():
            try:
                yield event('progress', phase='fetch')
                fetch = budget_candidates(request.category,request.countryCode) if request.countryCode else budget_candidates(request.category)
                candidates = await asyncio.wait_for(fetch, timeout=45)
                candidates = filter_country([*region_history(registry.values()), *candidates],request.countryCode)
                yield event('progress', phase='compare')
                chosen = choose_budget_destinations(candidates, request, request.budget, request.category)
                yield event('progress', phase='sights')
                verified = await confirmed_destinations([priced for _,priced in chosen],days=request.days)
                if not verified:
                    raise HTTPException(404,'예산 안에서 선택한 기간의 일정을 만들 만큼 관광명소가 충분한 여행지를 찾지 못했어요. 여행 기간을 줄이거나 국가·예산을 바꿔주세요.')
                yield event('progress', phase='names')
                cities = await asyncio.gather(*(localize_destination_label(priced, allow_original=True)
                                                for priced in verified))
                for city in cities:
                    remember(city)
                yield event('result', cities=cities, budget=request.budget, budgetBasis='upperEstimate')
            except HTTPException as error:
                yield event('error', status=error.status_code, message=error.detail)
            except asyncio.TimeoutError:
                yield event('error', status=504, message='여행지 조회가 지연되고 있어요. 다시 시도해주세요.')
        return StreamingResponse(stream(), media_type='application/x-ndjson', headers={
            'Cache-Control':'no-cache', 'X-Accel-Buffering':'no'})

    @app.post('/api/destinations/restore')
    async def restore_destinations(request: RestoreRequest):
        cities = []
        for saved in request.cities:
            city = saved.model_dump(exclude_none=True)
            require_destination(city)
            city.update(source='저장한 여행 계획', satisfaction=75, costIsEstimate=True)
            if city['category'] == 'domestic':
                city['countryCode'] = 'kr'
            elif city.get('countryCode'):
                city = as_overseas_region(city)
            if not city['recommendedPlaces'] and city.get('destinationType') != 'region':
                city['recommendedPlaces'] = [city.get('originalName') or city['cityName'].split(' · ')[0]]
            if not korean_only(city.get('displayName')):
                city.pop('displayName', None)
            cities.append(priced_city(city, request))
        restored = await asyncio.gather(*(localize_destination_label(city, allow_original=True) for city in cities))
        for city in restored:
            remember(city)
        return {'cities':restored}

    @app.post('/api/nearby-places')
    async def nearby(request: NearbyRequest):
        return await nearby_places(find_city(request.cityName))

    @app.post('/api/place-details')
    async def details(request: PlaceDetailsRequest):
        return await place_details(request.placeId, request.lat, request.lng)

    @app.post('/api/day-route')
    async def route(request: DayRouteRequest):
        return await daily_route(find_city(request.cityName), request.placeNames, request.mode)
