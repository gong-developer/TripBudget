"""Check a live Geoapify country boundary and country-restricted city results."""
import asyncio
from pathlib import Path
import sys

from dotenv import load_dotenv
from fastapi import HTTPException

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
load_dotenv(ROOT/'.env')
from app.geoapify_destinations import overseas_candidates


if __name__=='__main__':
    code=sys.argv[1] if len(sys.argv)>1 else 'jp'
    try:
        cities=asyncio.run(overseas_candidates(country_code=code))
        assert cities and all(city['countryCode']==code for city in cities)
        print(f'Country API check OK: {code}, {len(cities)} cities, no other-country results')
    except HTTPException as error:
        print(f'Country API check failed ({error.status_code}): {error.detail}')
        sys.exit(1)
