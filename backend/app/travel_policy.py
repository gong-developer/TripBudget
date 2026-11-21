"""Country exclusions for ordinary South Korean leisure travel.

Reviewed 2026-11-04, MOFA country-wide travel bans (through 2027-01-31):
https://0404.go.kr/bbs/contsPst/MST0000000000101/1/detail
North Korea is excluded separately at the product owner's request.
Partial-country advisories are NOT represented as country-wide bans here.
Review this list when MOFA changes its designations; it is not a live feed.
"""
from fastapi import HTTPException

REVIEWED_ON = '2026-11-04'
SOURCE_URL = 'https://0404.go.kr/bbs/contsPst/MST0000000000101/1/detail'
EXCLUDED_COUNTRIES = {
    'kp':('북한','조선민주주의인민공화국','North Korea',"Democratic People's Republic of Korea"),
    'af':('아프가니스탄','Afghanistan'),
    'iq':('이라크','Iraq'),
    'so':('소말리아','Somalia'),
    'ye':('예멘','Yemen'),
    'ly':('리비아','Libya'),
    'ua':('우크라이나','Ukraine'),
    'sd':('수단','Sudan'),
    'ht':('아이티','Haiti'),
    'ml':('말리','Mali'),
    'ir':('이란','Iran'),
}
ALIASES = {name.casefold():code for code,names in EXCLUDED_COUNTRIES.items() for name in names}


def destination_country(city):
    code = str(city.get('countryCode') or city.get('country_code') or '').lower()
    if code:
        return code
    if city.get('category') == 'domestic':
        return 'kr'
    for field in ('cityName','displayName','country'):
        for part in str(city.get(field) or '').split(' · '):
            if part.strip().casefold() in ALIASES:
                return ALIASES[part.strip().casefold()]
    return ''


def allowed_destination(city):
    return destination_country(city) not in EXCLUDED_COUNTRIES


def require_country(code):
    if str(code or '').lower() in EXCLUDED_COUNTRIES:
        raise HTTPException(422, '북한 또는 국가 전역 여행금지 대상은 추천하지 않아요. 다른 여행지를 선택해주세요.')


def require_destination(city):
    require_country(destination_country(city))
