from functools import lru_cache
import json
from pathlib import Path
import random
from fastapi import HTTPException

CATALOG_PATH=Path(__file__).resolve().parents[1]/'data'/'world_cities.json'

@lru_cache(maxsize=1)
def load_city_catalog():
    try:
        cities=json.loads(CATALOG_PATH.read_text(encoding='utf-8'))['cities']
        if not cities: raise ValueError('Empty catalog')
        return tuple(cities)
    except (OSError,ValueError,KeyError):
        raise HTTPException(503,'해외 도시 목록을 불러오지 못했어요. 도시 데이터 파일을 확인해주세요.') from None

def random_catalog_city():
    entry=random.choice(load_city_catalog())
    return catalog_city(entry)


def catalog_city(entry):
    return {'cityName':f"{entry['name']} · {entry['country']}",'displayName':f"{entry['name']} · {entry['country']}",
            'lat':entry['lat'],'lng':entry['lng'],'category':'international','countryCode':entry['countryCode'],
            'originalName':entry['originalName'],'geonameId':entry['geonameId'],'satisfaction':75,
            'recommendedPlaces':[entry['name']],'costIsEstimate':True,'nameLocalized':True,
            'source':'GeoNames (CC BY 4.0)'}
