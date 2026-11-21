import re
from app.city_catalog import load_city_catalog,random_catalog_city
from scripts.update_city_catalog import build_catalog

def test_catalog_contains_valid_korean_named_overseas_cities():
    cities=load_city_catalog()
    assert len(cities)>=100
    assert len({c['geonameId'] for c in cities})==len(cities)
    for city in cities:
        assert city['countryCode']!='kr'
        assert re.search('[가-힣]',city['name'])
        assert -90<=city['lat']<=90 and -180<=city['lng']<=180
        assert re.search('[가-힣]',city['country'])

def test_every_draw_belongs_to_catalog():
    ids={c['geonameId'] for c in load_city_catalog()}
    for _ in range(50):
        city=random_catalog_city()
        assert city['geonameId'] in ids
        assert city['displayName']==city['cityName']
        assert city['nameLocalized']

def test_importer_excludes_ocean_invalid_and_untranslated_rows():
    def row(identifier,name,aliases,code='PE',lat='-12',feature='P'):
        return '\t'.join([str(identifier),name,name,aliases,lat,'-77',feature,'PPL',code,'','','','','','100000','','','UTC','2026-01-01'])
    text='\n'.join([row(1,'Lima','리마'),row(2,'Unknown',''),row(3,'Seoul','서울','KR'),
                    row(4,'Bad','잘못된도시',lat='100'),row(5,'Ocean','바다',feature='H'),row(1,'Lima','리마')])
    cities=build_catalog(text)
    assert len(cities)==1
    assert cities[0]['name']=='리마'
