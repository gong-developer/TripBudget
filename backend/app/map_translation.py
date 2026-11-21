"""Registered-name lookup only. Legacy machine translations are never read."""
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field
from .place_names import CITIES, korean_only


class MapTranslationRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    names: list[Annotated[str, Field(min_length=1, max_length=128)]] = Field(min_length=1, max_length=24)


async def translate_labels(names):
    # The old labels SQLite table is intentionally ignored, including cached
    # Hangul strings. Hangul alone is not evidence of a correct proper name.
    translations = {}
    for name in dict.fromkeys(name.strip() for name in names if isinstance(name,str) and name.strip()):
        label = CITIES.get(name.casefold())
        if korean_only(label):
            translations[name] = label
    return {'translations': translations, 'available': True}


def install_map_translation(app):
    @app.post('/api/map/translate', summary='등록 한국어 지명 조회', tags=['명소와 지도 경로'])
    async def map_translate(request: MapTranslationRequest):
        return await translate_labels(request.names)
