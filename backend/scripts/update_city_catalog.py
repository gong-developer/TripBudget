"""Build an attributed, Korean-named destination catalog from GeoNames cities15000."""
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import re
import sys
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.place_names import COUNTRIES, CITIES

SOURCE='https://download.geonames.org/export/dump/cities15000.zip'

def build_catalog(text):
    result=[]
    for line in text.splitlines():
        fields=line.split('\t')
        if len(fields)<19: continue
        code=fields[8].lower()
        if code=='kr' or code not in COUNTRIES or fields[6]!='P': continue
        names=[fields[1],fields[2],*fields[3].split(',')]
        korean=next((CITIES[name.casefold()] for name in names if name.casefold() in CITIES),None)
        if not korean:
            korean=next((name for name in names if re.fullmatch(r'[가-힣][가-힣\s·\-]{1,79}',name)),None)
        if not korean: continue
        try:
            lat,lng=float(fields[4]),float(fields[5])
            if not (-90<=lat<=90 and -180<=lng<=180): continue
            result.append({'geonameId':int(fields[0]),'name':korean,'originalName':fields[1],
                           'countryCode':code,'country':COUNTRIES[code],'lat':lat,'lng':lng,
                           'population':int(fields[14] or 0)})
        except ValueError: continue
    return list({city['geonameId']:city for city in result}.values())

if __name__=='__main__':
    request=urllib.request.Request(SOURCE,headers={'User-Agent':'TripBudget/1.0'})
    with urllib.request.urlopen(request,timeout=40) as response: archive=response.read()
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        cities=build_catalog(bundle.read('cities15000.txt').decode('utf-8'))
    if len(cities)<100: raise RuntimeError('Unexpectedly small catalog; existing catalog was not overwritten.')
    target=ROOT/'data'/'world_cities.json'
    target.parent.mkdir(parents=True,exist_ok=True)
    content={'source':SOURCE,'attribution':'GeoNames, CC BY 4.0, https://www.geonames.org/',
             'updatedAt':datetime.now(timezone.utc).isoformat(),'cities':cities}
    temporary=target.with_suffix('.tmp')
    temporary.write_text(json.dumps(content,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    temporary.replace(target)
    print(f'Catalog ready: {len(cities)} cities across {len({c["countryCode"] for c in cities})} countries.')
