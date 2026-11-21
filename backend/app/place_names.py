"""Korean display names; provider originals remain separate metadata."""
import asyncio
import re
import math
import unicodedata
from functools import lru_cache
from fastapi import HTTPException

COUNTRIES = dict(pair.split(':') for pair in (
    'kr:대한민국 jp:일본 cn:중국 tw:대만 hk:홍콩 vn:베트남 th:태국 la:라오스 kh:캄보디아 '
    'mm:미얀마 my:말레이시아 sg:싱가포르 id:인도네시아 ph:필리핀 '
    'in:인도 np:네팔 bd:방글라데시 lk:스리랑카 mv:몰디브 pk:파키스탄 af:아프가니스탄 '
    'ir:이란 iq:이라크 sy:시리아 jo:요르단 lb:레바논 il:이스라엘 ps:팔레스타인 '
    'sa:사우디아라비아 ae:아랍에미리트 om:오만 ye:예멘 qa:카타르 kw:쿠웨이트 bh:바레인 '
    'tr:튀르키예 ge:조지아 am:아르메니아 az:아제르바이잔 kz:카자흐스탄 uz:우즈베키스탄 '
    'kg:키르기스스탄 tj:타지키스탄 tm:투르크메니스탄 mn:몽골 ru:러시아 '
    'us:미국 ca:캐나다 mx:멕시코 br:브라질 ar:아르헨티나 pe:페루 cl:칠레 co:콜롬비아 '
    'ec:에콰도르 bo:볼리비아 uy:우루과이 py:파라과이 ve:베네수엘라 cu:쿠바 cr:코스타리카 '
    'pa:파나마 gt:과테말라 hn:온두라스 ni:니카라과 sv:엘살바도르 jm:자메이카 '
    'gb:영국 fr:프랑스 de:독일 it:이탈리아 es:스페인 pt:포르투갈 nl:네덜란드 be:벨기에 '
    'ch:스위스 at:오스트리아 cz:체코 pl:폴란드 hu:헝가리 gr:그리스 hr:크로아티아 '
    'se:스웨덴 no:노르웨이 fi:핀란드 dk:덴마크 is:아이슬란드 ie:아일랜드 '
    'ro:루마니아 bg:불가리아 rs:세르비아 sk:슬로바키아 si:슬로베니아 ua:우크라이나 '
    'ee:에스토니아 lv:라트비아 lt:리투아니아 al:알바니아 ba:보스니아헤르체고비나 '
    'au:호주 nz:뉴질랜드 fj:피지 pg:파푸아뉴기니 '
    'eg:이집트 ma:모로코 tn:튀니지 dz:알제리 ly:리비아 za:남아프리카공화국 '
    'ke:케냐 tz:탄자니아 ug:우간다 et:에티오피아 gh:가나 ng:나이지리아 '
    'na:나미비아 bw:보츠와나 zm:잠비아 zw:짐바브웨 mg:마다가스카르 mu:모리셔스'
).split())
CITIES = {'london':'런던','lima':'리마','paris':'파리','tokyo':'도쿄','osaka':'오사카',
          'bangkok':'방콕','tehran':'테헤란','تهران':'테헤란','isfahan':'이스파한',
          'shiraz':'시라즈','rome':'로마','sydney':'시드니','new york':'뉴욕',
          'barcelona':'바르셀로나','madrid':'마드리드','berlin':'베를린','singapore':'싱가포르'}
CITIES.update({
    'yazd':'야즈드','یزد':'야즈드','shiraz':'시라즈','شیراز':'시라즈',
    'اصفهان':'이스파한','esfahan':'이스파한','mashhad':'마슈하드','مشهد':'마슈하드',
    'tabriz':'타브리즈','تبریز':'타브리즈','qom':'곰','قم':'곰','kerman':'케르만','کرمان':'케르만',
    'ahvaz':'아바즈','اهواز':'아바즈','rasht':'라슈트','رشت':'라슈트','qazvin':'카즈빈','قزوین':'카즈빈',
    'bushehr':'부셰르','بوشهر':'부셰르','hamedan':'하마단','همدان':'하마단',
    'nishapur':'니샤푸르','neyshabur':'니샤푸르','نیشابور':'니샤푸르',
    'moscow':'모스크바','москва':'모스크바','saint petersburg':'상트페테르부르크',
    'санкт-петербург':'상트페테르부르크','vladivostok':'블라디보스토크','владивосток':'블라디보스토크',
    'beijing':'베이징','北京':'베이징','shanghai':'상하이','上海':'상하이','京都':'교토',
    '京都市':'교토','大阪市':'오사카','東京':'도쿄','東京都':'도쿄','福岡市':'후쿠오카',
    'kyoto':'교토','fukuoka':'후쿠오카','sapporo':'삿포로','札幌市':'삿포로',
    'hanoi':'하노이','hà nội':'하노이','da nang':'다낭','đà nẵng':'다낭',
    'ho chi minh city':'호찌민','phuket':'푸껫','chiang mai':'치앙마이',
    'กรุงเทพมหานคร':'방콕','เชียงใหม่':'치앙마이','ภูเก็ต':'푸껫',
    'taipei':'타이베이','臺北市':'타이베이','台北市':'타이베이','hong kong':'홍콩',
    'lisbon':'리스본','lisboa':'리스본','porto':'포르투','prague':'프라하','praha':'프라하',
    'vienna':'빈','wien':'빈','budapest':'부다페스트','istanbul':'이스탄불',
    'athens':'아테네','αθήνα':'아테네','cairo':'카이로','القاهرة':'카이로',
    'dubai':'두바이','دبي':'두바이','marrakesh':'마라케시','marrakech':'마라케시',
    'melbourne':'멜버른','auckland':'오클랜드','toronto':'토론토','vancouver':'밴쿠버',
    'los angeles':'로스앤젤레스','san francisco':'샌프란시스코','chicago':'시카고',
    'buenos aires':'부에노스아이레스','santiago':'산티아고','bogota':'보고타','bogotá':'보고타',
})
NAME_POLICY = 'registered-v1'
REJECTED_NAMES = {'전체메뉴','전체 메뉴','주 메뉴','메뉴','스낵 바','스낵바','숙박 약관','채용정보','팟캐스트','카테고리','인기 카테고리','프로모션','이름 미제공','명소 이름 재조회 필요','여행지 이름 재조회 필요'}


def normalized_name(name):
    return ''.join(c for c in unicodedata.normalize('NFKD', name.casefold())
                   if c.isalnum())


@lru_cache(maxsize=1)
def catalog_name_index():
    # A name dictionary only: destinations still come from the live provider.
    from .city_catalog import load_city_catalog
    names, countries = {}, {}
    try:
        for entry in load_city_catalog():
            code = entry['countryCode'].lower()
            countries[code] = entry['country']
            for name in {entry['originalName'], entry['name']}:
                names.setdefault((code, normalized_name(name)), []).append(entry)
    except HTTPException:
        pass
    return names, countries


def local_names(row):
    original = str(row.get('city') or row.get('name') or '').strip()
    code = str(row.get('country_code') or '').lower()
    names, countries = catalog_name_index()
    matches = names.get((code, normalized_name(original)), [])
    # Namesakes in the same country require a matching location, not just a name.
    if row.get('lat') is not None and row.get('lon') is not None:
        try:
            lat, lon = float(row['lat']), float(row['lon'])
            matches = [entry for entry in matches
                       if math.hypot(entry['lat']-lat, (entry['lng']-lon)*math.cos(math.radians(lat))) <= .3]
        except (ValueError, TypeError):
            matches = []
    labels = {entry['name'] for entry in matches}
    city = original if korean_only(original) else (next(iter(labels)) if len(labels) == 1 else CITIES.get(original.casefold()))
    original_country = row.get('country') or ''
    country = COUNTRIES.get(code) or countries.get(code) or (original_country if korean_only(original_country) else None)
    return city, country

def korean_only(value):
    return (isinstance(value,str) and bool(re.search('[가-힣]',value))
            and bool(re.fullmatch(r'[가-힣0-9\s·.,()\-]+',value)) and len(value)<=200
            and value.strip() not in REJECTED_NAMES
            and not any(marker in value for marker in ('번역 미확인','도시명 확인 중','한글 변환 중')))

def latin_name(value):
    """Only send Latin-script input to the installed English translation model."""
    return (isinstance(value, str) and bool(value.strip()) and len(value) <= 200
            and any(char.isalpha() for char in value)
            and all(not char.isalpha() or 'LATIN' in unicodedata.name(char, '') for char in value))


async def local_translations(names):
    """Compatibility helper: registered dictionary only, with no machine API."""
    return {name:CITIES[name.casefold()] for name in names
            if isinstance(name,str) and name.casefold() in CITIES}


async def korean_names(client, row):
    """Use country/location-aware names; preserve originals when unregistered."""
    original=str(row.get('city') or row.get('name') or '').strip()
    city,country=local_names(row)
    english=(row.get('name_international') or {}).get('en') if isinstance(row.get('name_international'),dict) else None
    if not city and isinstance(english,str):
        city,_=local_names({**row,'city':english})
    raw_country=str(row.get('country') or row.get('country_code') or '').strip()
    country=country or (str(row.get('country_code') or '').upper() if raw_country in REJECTED_NAMES else raw_country)
    return city or original,country,bool(city and korean_only(city) and korean_only(country))


async def localize_destination_label(city, *, allow_original=False):
    """Discard old derived labels and retain the original API identity."""
    if city.get('namePolicy')==NAME_POLICY and isinstance(city.get('displayName'),str):
        return city
    original=city['cityName']
    parts=original.split(' · ')
    source_name=city.get('originalName') or parts[0]
    if source_name in REJECTED_NAMES:
        raise HTTPException(409,'이전 결과의 지명을 확인할 수 없어요. 여행지를 다시 조회해주세요.')
    if any(marker in source_name for marker in ('번역 미확인','도시명 확인 중')):
        raise HTTPException(409,'이전 결과에 원래 지명이 없어 확인할 수 없어요. 여행지를 다시 조회해주세요.')
    row={'city':source_name,'country':' · '.join(parts[1:]),
         'name_international':{'en':city.get('englishName')},
         'country_code':city.get('countryCode','kr' if city.get('category')=='domestic' else ''),
         'lat':city['lat'],'lon':city['lng']}
    try:
        name,country,localized=await korean_names(None,row)
    except (HTTPException,asyncio.TimeoutError):
        if not allow_original:
            raise
        _,country=local_names(row)
        name=source_name
        country=country or row['country']
        localized=False
    clean={key:value for key,value in city.items() if key not in ('nameTranslationNotice','displayName')}
    label=' · '.join(value for value in (name,country) if value)
    result={**clean,'displayName':label or source_name,'originalName':source_name,
            'nameLocalized':localized,'namePolicy':NAME_POLICY}
    if not localized:
        result['nameTranslationNotice']='등록된 한국어 지명을 확인하지 못해 원어 이름을 표시합니다.'
    return result
