import os,json
from pathlib import Path
from datetime import datetime,timezone
os.environ["DATABASE_PATH"]=str(__import__("pathlib").Path(__import__("tempfile").gettempdir()) / "sentinel-public-tests.db")
os.environ["API_KEY"]="test-only-key"
from sentinel.events.engine import EventEngine,Zone,Detection
from sentinel.storage.repository import Repository

def detection(x=50):return Detection(17,"person",.94,(x-10,20,x+10,50))
def engine():return EventEngine([Zone(id="A",name="A",polygon=[(0,0),(.8,0),(.8,1),(0,1)],dwell_seconds=3)],"CAM","SESSION",2)
def test_zone_lifecycle():
    e=engine();assert [r['event_type'] for r in e.update([detection()],100,100,100)]==['zone_enter']
    assert e.update([detection()],100,100,102)==[]
    assert [r['event_type'] for r in e.update([detection()],100,100,104)]==['zone_dwell']
    assert e.update([detection()],100,100,105)==[]
    out=e.update([detection(95)],100,100,106)
    assert out[0]['event_type']=='zone_exit' and out[0]['duration']==6
    assert e.update([detection()],100,100,107)[0]['event_type']=='zone_enter'
def test_occlusion_is_not_exit():
    e=engine();e.update([detection()],100,100,100)
    assert e.update([],100,100,101)==[]
    event=e.update([],100,100,103)[0]
    assert event['event_type']=='track_lost' and not event['metadata']['exit_confirmed']
def test_source_end_is_not_exit():
    e=engine();e.update([detection()],100,100,100)
    assert e.close(110,'source_ended')[0]['event_type']=='presence_ended'
def test_repository_persists_and_filters(tmp_path):
    path=str(tmp_path/'events.db');r=Repository(path);e=engine().update([detection()],100,100,100)[0];r.save([e])
    other=Repository(path);assert other.get(e['id'])['metadata']=={}
    assert len(other.query(camera='CAM'))==1 and other.query(camera='OTHER')==[]
    assert other.status(e['id'],'reviewed')==1 and other.get(e['id'])['status']=='reviewed'
    assert other.stats()[0]['count']==1

def test_api_auth_and_factual_context():
    from fastapi.testclient import TestClient
    from sentinel.api import app
    with TestClient(app) as c:
        assert c.get('/health').status_code==200
        assert c.get('/events').status_code==401
        h={'X-API-Key':'test-only-key'}
        assert c.get('/events',headers=h).status_code==200
        assert c.get('/events?limit=0',headers=h).status_code==422
        assert c.get('/events/missing',headers=h).status_code==404
        assert c.post('/cameras/start',headers=h,json={'kind':'file','source':'../../.env'}).status_code==400
        assert c.put('/zones',headers=h,json=[{'id':'bad','name':'bad','polygon':[[2,0],[1,1],[0,0]]}]).status_code==422
        a=c.post('/chat',headers=h,json={'minutes':10,'use_llm':False}).json()
        assert a['provider']=='structured' and 'answer' in a
        assert c.get('/reports',headers=h).status_code==200
        assert c.post('/chat',headers=h,json={'minutes':0}).status_code==422
        assert c.get('/').status_code==200


def test_api_date_normalization_and_ws_rejection():
    import pytest
    from fastapi.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect
    from sentinel.api import app
    with TestClient(app) as c:
        h={'X-API-Key':'test-only-key'}
        assert c.get('/events?since=bad',headers=h).status_code==422
        assert c.get('/events?since=2026-10-02T10:00:00',headers=h).status_code==400
        assert c.get('/events?since=2026-10-02T10:00:00-03:00',headers=h).status_code==200
        with c.websocket_connect('/ws/events') as ws:
            ws.send_json({'api_key':'bad'})
            with pytest.raises(WebSocketDisconnect):ws.receive_json()


def test_jpeg_validation_survives_optional_codec_patch(monkeypatch):
    import io
    from PIL import Image
    from types import SimpleNamespace
    from fastapi.testclient import TestClient
    import sentinel.api as api
    monkeypatch.setattr(api,'pipeline',SimpleNamespace(snapshot=lambda: {'kind':'push','status':'running'},process=lambda frame,**kwargs: {'accepted':True},stop=lambda: {}))
    image=Image.new('RGB',(100,100));encoded=io.BytesIO();image.save(encoded,format='JPEG')
    def optional_codec_patch(*args,**kwargs):raise ModuleNotFoundError('optional codec missing')
    monkeypatch.setattr(Image,'open',optional_codec_patch)
    with TestClient(api.app) as c:
        h={'X-API-Key':'test-only-key'}
        assert c.post('/frames',headers=h,files={'file':('bad.jpg',b'invalid','image/jpeg')}).status_code==400
        r=c.post('/frames',headers=h,files={'file':('frame.jpg',encoded.getvalue(),'image/jpeg')})
        assert r.status_code==200 and r.json()['accepted']


def test_server_webcam_index_default_and_validation(monkeypatch):
    from types import SimpleNamespace
    from fastapi.testclient import TestClient
    import sentinel.api as api
    calls=[]
    monkeypatch.setattr(api,'pipeline',SimpleNamespace(start=lambda *args:calls.append(args),snapshot=lambda: {'status':'starting'},stop=lambda: {}))
    with TestClient(api.app) as c:
        h={'X-API-Key':'test-only-key'}
        assert c.post('/cameras/start',headers=h,json={'kind':'webcam','source':''}).status_code==200
        assert calls[-1][1]=='0'
        assert c.post('/cameras/start',headers=h,json={'kind':'webcam','source':' 1 '}).status_code==200
        assert calls[-1][1]=='1'
        for invalid in ['demo-bus.avi','-1','100','²']:
            assert c.post('/cameras/start',headers=h,json={'kind':'webcam','source':invalid}).status_code==400
