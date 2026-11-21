"""TourAPI domestic covers, Unsplash overseas covers, and Commons fallbacks."""
import asyncio
from collections import OrderedDict
from html.parser import HTMLParser
import time
import os
import re
import unicodedata
from urllib.parse import urlparse, unquote

import httpx
from fastapi import HTTPException
from .costs import distance

CACHE = OrderedDict()
INFLIGHT = {}
SLOTS = asyncio.Semaphore(3)


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, text):
        self.parts.append(text)


def plain(value):
    parser = PlainText()
    parser.feed(str(value or '')[:10000])
    return ' '.join(' '.join(parser.parts).split())[:400]


def safe_url(value, hosts):
    if not isinstance(value, str):
        return None
    try:
        parsed = urlparse(value)
        return value if parsed.scheme == 'https' and parsed.hostname in hosts and not parsed.username else None
    except ValueError:
        return None


def domestic(city):
    return city.get('countryCode') == 'kr' or city.get('category') == 'domestic'


def image_license(value):
    return value.startswith(('CC BY', 'CC0')) or value.lower() in ('public domain', 'kogl type 1')


def name_key(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value)).casefold() if c.isalnum())


async def tour_photo(city):
    from .domestic_sights import domestic_sights
    # The sight provider validates both province and district, so a photo from
    # a neighbouring administrative region cannot become this region's cover.
    sights = (await domestic_sights(city, limit=12))['places']
    key = unquote(os.getenv('TOUR_API_KEY', '').strip())
    async with httpx.AsyncClient(timeout=6) as client:
        async def images(place):
            if not str(place.get('contentId') or '').isdigit():
                return None
            try:
                response = await client.get('https://apis.data.go.kr/B551011/KorService2/detailImage2', params={
                    'serviceKey':key,'MobileOS':'ETC','MobileApp':'TripRoulette','_type':'json',
                    'contentId':place['contentId'],'imageYN':'Y','numOfRows':10,'pageNo':1})
                response.raise_for_status()
                envelope = response.json()['response']
                if str(envelope['header']['resultCode']) != '0000':
                    return None
                rows = (envelope['body'].get('items') or {}).get('item') or []
                for row in ([rows] if isinstance(rows, dict) else rows):
                    if row.get('cpyrhtDivCd') != 'Type1':
                        continue
                    raw = row.get('originimgurl') or ''
                    # TourAPI publishes HTTP URLs; the same image host supports HTTPS.
                    url = safe_url(raw.replace('http://', 'https://', 1), {'tong.visitkorea.or.kr'})
                    if url:
                        return {'url':url,'sourceUrl':url,'title':place['name'],
                                'author':'한국관광공사 제공','license':'공공누리 제1유형',
                                'licenseUrl':'https://www.kogl.or.kr/info/license.do',
                                'source':'TourAPI','subjectType':'sight'}
            except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
                return None
        candidates = await asyncio.gather(*(images(place) for place in sights[:3]))
        return next((photo for photo in candidates if photo), None)


async def commons_photo(city):
    async with asyncio.timeout(15):
        async with httpx.AsyncClient(timeout=6, headers={'User-Agent':'TripRoulette/1.0 (destination photos)', 'Accept-Encoding':'identity', 'Connection':'close'}) as client:
            async def query(host, **params):
                response = await client.get(f'https://{host}/w/api.php', params={'action':'query','format':'json',**params})
                response.raise_for_status()
                return response.json().get('query', {}).get('pages', {})

            name = (city.get('originalName') or city['cityName']).split(' · ')[0]
            titles = [city.get('englishName') or name]
            language = 'ko' if domestic(city) or (not city.get('englishName') and re.search('[가-힣]', name)) else 'en'
            if language == 'en' and not city.get('englishName'):
                if re.search('[一-鿿ぁ-ヿ]', name):
                    language = 'ja' if city.get('countryCode') == 'jp' else 'zh'
                elif re.search('[؀-ۿ]', name):
                    language = {'ir':'fa','af':'ps'}.get(city.get('countryCode'), 'ar')
                elif re.search('[Ѐ-ӿ]', name):
                    language = {'ua':'uk','bg':'bg','rs':'sr'}.get(city.get('countryCode'), 'ru')
            if domestic(city):
                province = city['cityName'].split(' · ')[-1]
                if province != name:
                    titles.insert(0, f'{name} ({province})')
            properties = {'prop':'pageimages|coordinates|langlinks|pageprops','piprop':'name',
                          'lllang':'en','lllimit':5,'ppprop':'disambiguation'}
            pages = await query(f'{language}.wikipedia.org', titles='|'.join(dict.fromkeys(titles)), redirects=1, **properties)
            aliases = set(titles)
            if language != 'en':
                linked = [link['*'] for page in pages.values() for link in page.get('langlinks', []) if link.get('lang') == 'en']
                if linked:
                    aliases.update(linked)
                    english = await query('en.wikipedia.org', titles='|'.join(linked), redirects=1, **properties)
                    pages = {**pages, **{'en:'+key:value for key,value in english.items()}}

            def eligible(page):
                coords = page.get('coordinates') or []
                return (page.get('pageimage') and coords and 'disambiguation' not in page.get('pageprops', {})
                        and distance(city['lat'],city['lng'],coords[0]['lat'],coords[0]['lon']) <= 40)

            candidates = [page for page in pages.values() if eligible(page)]
            if not candidates:
                # Resolve ambiguous names (e.g. Bata) using articles near the
                # selected city, still requiring its name and coordinates to match.
                nearby = await query('en.wikipedia.org', generator='geosearch',
                    ggscoord=f"{city['lat']}|{city['lng']}", ggsradius=10000, ggslimit=8, **properties)
                keys = {name_key(alias.split(' (')[0].split(',')[0]) for alias in aliases}
                candidates = [page for page in nearby.values() if eligible(page)
                              and name_key(page.get('title','').split(' (')[0].split(',')[0]) in keys]
            for page in candidates:
                image = page['pageimage']
                files = await query('commons.wikimedia.org', titles=f'File:{image}', prop='imageinfo',
                                    iiprop='url|mime|extmetadata', iiurlwidth=960)
                for file in files.values():
                    info = (file.get('imageinfo') or [{}])[0]
                    metadata = info.get('extmetadata') or {}
                    value = lambda key: plain((metadata.get(key) or {}).get('value'))
                    license_name = value('LicenseShortName')
                    url = safe_url(info.get('thumburl') or info.get('url'), {'upload.wikimedia.org','thumb.wikimedia.org'})
                    source = safe_url(info.get('descriptionurl'), {'commons.wikimedia.org'})
                    if url:
                        url = url.split('?', 1)[0]
                    if not url or not source or info.get('mime') not in ('image/jpeg','image/png','image/webp') or not image_license(license_name):
                        continue
                    return {'url':url,'sourceUrl':source,'title':value('ObjectName') or image,
                            'author':value('Artist') or value('Credit') or 'Wikimedia Commons contributors',
                            'license':license_name,'source':'Wikimedia Commons'}
    return None


async def lookup_photo(city):
    async with SLOTS, asyncio.timeout(35):
        if not domestic(city):
            from .unsplash_photos import unsplash_photo
            try:
                async with asyncio.timeout(17):
                    photo = await unsplash_photo(city)
                if photo:
                    return photo
            except TimeoutError:
                pass
        if domestic(city) and city.get('regionId'):
            try:
                async with asyncio.timeout(20):
                    photo = await tour_photo(city)
                if photo:
                    return photo
            except (HTTPException, httpx.HTTPError, TimeoutError, ValueError, TypeError, KeyError):
                pass
        return await commons_photo(city)


async def destination_photo(city):
    key = (city['cityName'], city['lat'], city['lng'])
    now = time.monotonic()
    if key in CACHE and CACHE[key][0] > now:
        CACHE.move_to_end(key)
        return CACHE[key][1]
    task = INFLIGHT.get(key)
    if task is None:
        async def fetch():
            try:
                photo = await lookup_photo(city)
            except (httpx.HTTPError, TimeoutError, ValueError, TypeError, KeyError, AttributeError, IndexError):
                photo = None
            CACHE[key] = (time.monotonic() + (86400 if photo else 300), photo)
            CACHE.move_to_end(key)
            while len(CACHE) > 256:
                CACHE.popitem(last=False)
            return photo
        task = asyncio.create_task(fetch())
        INFLIGHT[key] = task
        task.add_done_callback(lambda done: INFLIGHT.pop(key, None))
    return await asyncio.shield(task)
