"""Verify one live recommendation request without printing credentials."""
import asyncio
from pathlib import Path
import sys

from dotenv import load_dotenv
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / '.env')
from app.geoapify_destinations import overseas_candidates

if __name__ == '__main__':
    try:
        cities = asyncio.run(overseas_candidates(batches=1))
        print(f'Geoapify live check OK: {len(cities)} valid overseas city candidates')
    except HTTPException as error:
        print(f'Geoapify check failed ({error.status_code}): {error.detail}')
        sys.exit(1)
