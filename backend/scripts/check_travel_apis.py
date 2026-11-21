"""Verify nearby sights, place details and routing without Gemini calls."""
import asyncio
from pathlib import Path
import sys

from dotenv import load_dotenv
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / '.env')
from app.travel_services import nearby_places, place_details, daily_route


async def check():
    city={'cityName':'Paris · France','lat':48.8566,'lng':2.3522,'countryCode':'fr'}
    nearby=await nearby_places(city)
    print(f'Nearby places: {len(nearby["places"])} valid results')
    if len(nearby['places'])<2:
        raise HTTPException(404,'Not enough nearby places for a route check')
    first=nearby['places'][0]
    second=max(nearby['places'][1:],key=lambda place:(place['lat']-first['lat'])**2+(place['lng']-first['lng'])**2)
    details=await place_details(first.get('placeId'),first['lat'],first['lng'])
    print('Place Details API: OK; opening hours provided:',bool(details['openingHours']))
    route=await daily_route(city,[first['name'],second['name']],'walk')
    print(f'Routing API: OK; {len(route["lines"])} geometry lines, {route["distance"]:.0f} metres')


if __name__=='__main__':
    try:
        asyncio.run(check())
    except HTTPException as error:
        print(f'Travel API check failed ({error.status_code}): {error.detail}')
        sys.exit(1)
