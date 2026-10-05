from sentinel.storage.repository import Repository
from sentinel.events.engine import EventEngine,Zone,Detection
from fastapi.testclient import TestClient
import pytest

def event(session='S'):
 e=EventEngine([Zone(id='Z',name='Z',polygon=[(0,0),(1,0),(1,1),(0,1)])],'C',session)
 return e.update([Detection(1,'person',.9,(10,10,30,30))],100,100,10)[0]

def test_review_history_and_session_scoped_export(tmp_path):
 r=Repository(str(tmp_path/'db'));a=event();b=event('OTHER');r.save([a,b])
 assert r.review(a['id'])['verdict']=='not_reviewed'
 r.review_save(a['id'],'incorrect','box wrong');r.review_save(a['id'],'uncertain','revised');r.review_save(b['id'],'confirmed','other')
 rows=r.review_export('S');assert len(rows)==1 and rows[0]['verdict']=='uncertain'
 with r.connect() as c:assert c.execute('SELECT COUNT(*) FROM event_reviews').fetchone()[0]==3
 assert r.get(a['id'])['status']=='new'
 with pytest.raises(ValueError):r.review_save('missing','uncertain','')

def test_review_api_auth_validation_and_no_invented_evidence(monkeypatch,tmp_path):
 from sentinel import api
 r=Repository(str(tmp_path/'db'));e=event();r.save([e]);monkeypatch.setattr(api,'repo',r)
 c=TestClient(api.app);h={'X-API-Key':api.settings.api_key};path='/events/'+e['id']+'/review'
 assert c.post(path,json={'verdict':'incorrect'}).status_code==401
 assert c.post(path,headers=h,json={'verdict':'confirmed'}).status_code==400
 assert c.post(path,headers=h,json={'verdict':'whatever'}).status_code==422
 assert c.post(path,headers=h,json={'verdict':'uncertain','note':'x'*801}).status_code==422
 assert c.post(path,headers=h,json={'verdict':'uncertain','note':'no image'}).status_code==200
 assert c.get(path,headers=h).json()['note']=='no image'
 assert c.get('/evaluation/reviews',headers=h,params={'session_id':'OTHER'}).json()['items']==[]
