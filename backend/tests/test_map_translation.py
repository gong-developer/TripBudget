import asyncio
import sqlite3
import httpx
from fastapi.testclient import TestClient
from app.main import app
from app import map_translation as translation


def test_registered_names_work_without_any_translator(monkeypatch):
    def unexpected_client(**kwargs):
        raise AssertionError('Place-name lookup must not call machine translation')
    monkeypatch.setattr(httpx,'AsyncClient',unexpected_client)
    response=TestClient(app).post('/api/map/translate',json={'names':['Tokyo','Paris','Tokyo']})
    assert response.json()=={'translations':{'Tokyo':'도쿄','Paris':'파리'},'available':True}


def test_legacy_bad_cache_is_ignored_and_preserved(tmp_path,monkeypatch):
    path=tmp_path/'labels.sqlite3'
    monkeypatch.setenv('MAP_TRANSLATION_CACHE',str(path))
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE labels(name TEXT PRIMARY KEY,korean TEXT NOT NULL)')
        db.executemany('INSERT INTO labels VALUES (?,?)',[
            ('Seomyeon Shopping District','전체메뉴'),('Valdosta','스낵 바'),
            ('Stench Monument','숙박 약관'),('Tokyo','잘못된 도쿄')])
    def forbidden(**kwargs):
        raise AssertionError('No remote or local translation call is permitted')
    monkeypatch.setattr(httpx,'AsyncClient',forbidden)
    result=asyncio.run(translation.translate_labels(['Seomyeon Shopping District','Valdosta','Stench Monument','Tokyo']))
    assert result=={'translations':{'Tokyo':'도쿄'},'available':True}
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT count(*) FROM labels').fetchone()[0]==4


def test_unknown_names_are_left_untranslated():
    assert asyncio.run(translation.translate_labels(['Unknown Place','Little Dead Key']))=={'translations':{},'available':True}


def test_lookup_input_is_bounded():
    client=TestClient(app)
    for names in ([],['a']*25,['a'*129]):
        assert client.post('/api/map/translate',json={'names':names}).status_code==422
