"""Build local country polygons from public-domain Natural Earth data."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import urllib.request

SOURCE = 'https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_admin_0_countries.geojson'
TARGET = Path(__file__).resolve().parents[1] / 'data' / 'countries.geojson'


def area(ring):
    return abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(ring,ring[1:]))) / 2


def rounded(value):
    if isinstance(value, list):
        return [rounded(child) for child in value]
    return round(value, 3)


def build(data):
    countries = {}
    for feature in data['features']:
        props, geometry = feature['properties'], feature['geometry']
        code = next((str(props.get(key, '')).lower() for key in ('ISO_A2_EH','ISO_A2','WB_A2')
                     if re.fullmatch('[A-Za-z]{2}', str(props.get(key, '')))), None)
        name = props.get('NAME_KO')
        if not code or not isinstance(name, str) or not re.search('[가-힣]', name):
            continue
        if geometry['type'] not in ('Polygon','MultiPolygon'):
            continue
        polygons = geometry['coordinates'] if geometry['type']=='MultiPolygon' else [geometry['coordinates']]
        largest = max(polygons,key=lambda polygon:area(polygon[0]))[0]
        bounds = [[min(point[1] for point in largest),min(point[0] for point in largest)],
                  [max(point[1] for point in largest),max(point[0] for point in largest)]]
        # All polygons remain clickable. Use the largest landmass only for camera framing.
        countries[code] = {'type':'Feature','properties':{
            'code':code,'name':name,'englishName':props.get('ADMIN') or props['NAME'],
            'bounds':rounded(bounds)},'geometry':{'type':geometry['type'],'coordinates':rounded(geometry['coordinates'])}}
    if len(countries) < 190 or not {'jp','kr','sg','fr','us'}.issubset(countries):
        raise ValueError('Incomplete country dataset; existing data was not overwritten')
    return {'type':'FeatureCollection','source':SOURCE,'attribution':'Natural Earth · Public domain',
            'features':sorted(countries.values(),key=lambda country:country['properties']['code'])}


if __name__=='__main__':
    request = urllib.request.Request(SOURCE, headers={'User-Agent':'TripBudget/1.0'})
    with urllib.request.urlopen(request,timeout=30) as response:
        raw = response.read()
    result = build(json.loads(raw))
    result.update(updatedAt=datetime.now(timezone.utc).isoformat(),sourceSha256=hashlib.sha256(raw).hexdigest())
    temporary = TARGET.with_suffix('.tmp')
    temporary.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    temporary.replace(TARGET)
    print(f'Country boundaries ready: {len(result["features"])} countries/regions; {TARGET.stat().st_size} bytes')
