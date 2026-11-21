"""Build region destinations from GeoNames administrative features, not attractions."""
import argparse
from datetime import datetime, timezone
from io import BytesIO
import json
from pathlib import Path
import re
from urllib.request import urlopen
from zipfile import ZipFile

SOURCE = 'https://download.geonames.org/export/dump/KR.zip'
# GeoNames province -> current Korean name, TourAPI province code.
PROVINCES = {
    '11':('서울특별시','1'), '12':('인천광역시','2'), '19':('대전광역시','3'),
    '15':('대구광역시','4'), '18':('광주광역시','5'), '10':('부산광역시','6'),
    '21':('울산광역시','7'), '22':('세종특별자치시','8'), '13':('경기도','31'),
    '06':('강원특별자치도','32'), '05':('충청북도','33'), '17':('충청남도','34'),
    '14':('경상북도','35'), '20':('경상남도','36'), '03':('전북특별자치도','37'),
    '16':('전라남도','38'), '01':('제주특별자치도','39'),
}


def build(archive):
    with ZipFile(BytesIO(archive)) as bundle:
        rows = [line.split('\t') for line in bundle.read('KR.txt').decode('utf-8').splitlines()]
    regions = []
    for row in rows:
        province, area = PROVINCES.get(row[10], ('', ''))
        metropolitan = area in ('1','2','3','4','5','6','7','8')
        if not province or row[7] != ('ADM1' if metropolitan else 'ADM2'):
            continue
        names = [name for name in row[3].split(',') if re.fullmatch(r'[가-힣]+[시군]', name)]
        if not metropolitan and not names:
            raise ValueError(f'Missing Korean administrative name: {row[0]}')
        name = province if metropolitan else names[-1]
        regions.append({'regionId':row[0], 'name':name, 'province':province,
                        'districtName':'' if metropolitan else name,
                        'areaCode':area, 'lat':float(row[4]), 'lng':float(row[5])})
    if len(regions) < 150 or len({r['province'] for r in regions}) != 17:
        raise ValueError('Incomplete domestic region data')
    return {'source':SOURCE, 'attribution':'GeoNames, CC BY 4.0, https://www.geonames.org/',
            'updatedAt':datetime.now(timezone.utc).isoformat(),
            'regions':sorted(regions, key=lambda r:(r['province'],r['name']))}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive', type=Path)
    args = parser.parse_args()
    archive = args.archive.read_bytes() if args.archive else urlopen(SOURCE, timeout=60).read()
    target = Path(__file__).resolve().parents[1] / 'data' / 'domestic_regions.json'
    payload = json.dumps(build(archive), ensure_ascii=False, indent=2) + '\n'
    temporary = target.with_suffix('.tmp')
    temporary.write_text(payload, encoding='utf-8')
    temporary.replace(target)
    print(f'{len(json.loads(payload)["regions"])} domestic regions written')
