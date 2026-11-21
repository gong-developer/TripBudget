"""Bounded Unsplash cover search; credentials stay in server request headers."""
import math
import os
import re
import time
import unicodedata
from urllib.parse import urlencode, urlparse, parse_qsl, urlunparse

import httpx
from fastapi import HTTPException
from .countries import country_info
from .costs import distance

UNAVAILABLE_UNTIL = 0


def normalize(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value or '')).casefold() if c.isalnum())


def trusted_url(value, host):
    if not isinstance(value, str):
        return None
    try:
        parsed = urlparse(value)
        return value if parsed.scheme == 'https' and parsed.hostname == host and not parsed.username else None
    except ValueError:
        return None


def referral(value):
    parsed = urlparse(value)
    query = dict(parse_qsl(parsed.query))
    query.update(utm_source='triproulette', utm_medium='referral')
    return urlunparse(parsed._replace(query=urlencode(query)))


def search_name(city):
    original = (city.get('originalName') or city['cityName']).split(' · ')[0]
    if city.get('englishName'):
        return city['englishName']
    if original.isascii():
        return original
    from .city_catalog import load_city_catalog
    aliases = {normalize(original),normalize((city.get('displayName') or '').split(' · ')[0])} - {''}
    if city.get('countryCode')=='jp' and original.endswith(('도','부','현','시')):
        aliases.add(normalize(original[:-1]))
    try:
        near = [row for row in load_city_catalog() if row['countryCode']==city.get('countryCode')
                and distance(city['lat'],city['lng'],row['lat'],row['lng']) <= 20
                and (normalize(row.get('name')) in aliases or normalize(row.get('originalName')) in aliases)]
        if near:
            closest = min(near,key=lambda row:distance(city['lat'],city['lng'],row['lat'],row['lng']))
            if closest.get('originalName'):
                return closest['originalName']
    except (HTTPException, ValueError, KeyError, TypeError):
        pass
    return original


def matching_location(photo, city, name, country):
    location = photo.get('location') or {}
    position = location.get('position') or {}
    lat, lng = position.get('latitude'), position.get('longitude')
    if lat is not None and lng is not None:
        try:
            lat, lng = float(lat),float(lng)
            return (math.isfinite(lat) and math.isfinite(lng) and -90<=lat<=90 and -180<=lng<=180
                    and distance(city['lat'],city['lng'],lat,lng)<=40)
        except (ValueError,TypeError):
            return False
    # Keyword relevance alone cannot establish that an image belongs here.
    names = {normalize(name),normalize(city.get('originalName')),normalize(city.get('englishName'))} - {''}
    countries = {normalize(country)}
    if city.get('countryCode') == 'us':
        countries.update({'unitedstates','usa','unitedstatesofamerica'})
    return normalize(location.get('city')) in names and normalize(location.get('country')) in countries


async def unsplash_photo(city):
    global UNAVAILABLE_UNTIL
    key = os.getenv('UNSPLASH_ACCESS_KEY','').strip()
    if not key or time.monotonic() < UNAVAILABLE_UNTIL:
        return None
    try:
        country = country_info(city.get('countryCode'))['englishName']
        name = search_name(city)
        headers = {'Authorization':'Client-ID '+key,'Accept-Version':'v1'}
        async with httpx.AsyncClient(timeout=5, headers=headers) as client:
            async def request(url, **kwargs):
                global UNAVAILABLE_UNTIL
                response = await client.get(url, **kwargs)
                if response.status_code in (401,403,429):
                    UNAVAILABLE_UNTIL = time.monotonic()+3600
                response.raise_for_status()
                return response.json()
            result = await request('https://api.unsplash.com/search/photos', params={
                'query':f'{name} {country}','orientation':'landscape','content_filter':'high','per_page':6})
            candidates = result.get('results') or []
            if not isinstance(candidates,list):
                return None
            candidates = [row for row in candidates if isinstance(row,dict)]
            candidates.sort(key=lambda row:normalize(name) not in normalize(str(row.get('description') or '')+' '+str(row.get('alt_description') or '')))
            for item in candidates[:2]:
                identifier = item.get('id')
                if not isinstance(identifier,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',identifier):
                    continue
                photo = item if item.get('location') else await request(f'https://api.unsplash.com/photos/{identifier}')
                if not isinstance(photo,dict) or not matching_location(photo,city,name,country):
                    continue
                image = trusted_url((photo.get('urls') or {}).get('regular'),'images.unsplash.com')
                link = trusted_url((photo.get('links') or {}).get('html'),'unsplash.com')
                user = photo.get('user') or {}
                author = user.get('name')
                author_url = trusted_url((user.get('links') or {}).get('html'),'unsplash.com')
                if not image or not link or not author_url or not isinstance(author,str) or not author:
                    continue
                # Choosing this photo as the regional cover is a download-like
                # use. Track once per server cover selection, not for every view.
                tracking = trusted_url((photo.get('links') or {}).get('download_location'),'api.unsplash.com')
                if tracking and urlparse(tracking).path == f'/photos/{identifier}/download':
                    try:
                        await client.get(tracking,timeout=2)
                    except httpx.HTTPError:
                        pass
                return {'url':image,'sourceUrl':referral(link),'authorUrl':referral(author_url),
                        'title':str(photo.get('alt_description') or photo.get('description') or name)[:300],
                        'author':author[:200],'license':'Unsplash License','licenseUrl':'https://unsplash.com/license',
                        'source':'Unsplash','subjectType':'region'}
    except (HTTPException,httpx.HTTPError,ValueError,KeyError,TypeError,AttributeError,IndexError):
        return None
    return None
