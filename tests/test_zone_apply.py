import json,time
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from sentinel.events.engine import Zone,EventEngine,Detection
from sentinel.storage.repository import Repository
import sentinel.api as api

@pytest.fixture
def zone_client(tmp_path,monkeypatch):
    import threading
    old=Zone(id='OLD',name='Anterior',polygon=[(0,0),(1,0),(1,1),(0,1)],dwell_seconds=1)
    engine=EventEngine([old],'CAM','SESSION',2)
    engine.update([Detection(1,'person',.9,(10,10,30,30))],100,100,time.time()-3)
    path=tmp_path/'zones.json';path.write_text(json.dumps([old.model_dump()]))
    repository=Repository(str(tmp_path/'db.sqlite'))
    pipeline=SimpleNamespace(lock=threading.RLock(),engine=engine,tracker=object(),state='running',snapshot=lambda:{'status':pipeline.state,'camera':'CAM','session_id':'SESSION'},stop=lambda:{})
    monkeypatch.setattr(api,'repo',repository);monkeypatch.setattr(api,'pipeline',pipeline);monkeypatch.setattr(api.settings,'zones_path',str(path))
    with TestClient(api.app) as client:yield client,pipeline,repository,path,{'X-API-Key':api.settings.api_key}

def new_zone():return dict(id='NEW',name='Porta',polygon=[[0,0],[.5,0],[.5,.5],[0,.5]],dwell_seconds=5)

def test_hot_apply_keeps_tracker_and_camera_and_records_rule_boundary(zone_client):
    c,p,r,path,h=zone_client;tracker=p.tracker
    response=c.post('/zones/apply',headers=h,json=[new_zone()])
    assert response.status_code==200 and response.json()['processing_preserved']
    assert p.tracker is tracker and p.engine.session=='SESSION' and p.engine.camera=='CAM'
    assert p.engine.zones[0].id=='NEW' and not p.engine.active
    events=r.query();assert len(events)==1 and events[0]['event_type']=='presence_ended'
    assert events[0]['metadata']['reason']=='zones_changed' and not events[0]['metadata']['exit_confirmed']
    assert r.evidence(events[0]['id']) is None
    assert json.loads(path.read_text())[0]['id']=='NEW'

def test_invalid_or_duplicate_area_does_not_change_active_rule(zone_client):
    c,p,r,path,h=zone_client;before=path.read_text();engine=p.engine
    assert c.post('/zones/apply',headers=h,json=[new_zone(),new_zone()]).status_code==400
    invalid=new_zone();invalid['polygon']=[[0,0],[0,0],[0,0]]
    assert c.post('/zones/apply',headers=h,json=[invalid]).status_code==422
    assert path.read_text()==before and p.engine is engine and p.engine.active and not r.query()

def test_startup_conflict_and_unauthorized_apply_leave_state_unchanged(zone_client):
    c,p,r,path,h=zone_client;before=path.read_text()
    assert c.post('/zones/apply',json=[new_zone()]).status_code==401
    p.state='starting'
    assert c.post('/zones/apply',headers=h,json=[new_zone()]).status_code==409
    assert path.read_text()==before and not r.query()
