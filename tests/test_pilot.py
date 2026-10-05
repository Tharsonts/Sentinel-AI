from sentinel.evaluation import trial_summary
from sentinel.storage.repository import Repository
from fastapi.testclient import TestClient

def test_pairs_failures_and_negative_gain():
 rows=[dict(task_id='A',mode='manual',seconds=60,outcome='correct'),dict(task_id='A',mode='sentinel',seconds=120,outcome='incorrect'),dict(task_id='B',mode='sentinel',seconds=1,outcome='correct')]
 s=trial_summary(rows);assert s['pairs']==1 and s['median_minutes_saved']==-1 and s['correct']['sentinel']==0 and not s['suitable_for_estimate']
 assert trial_summary([])['median_minutes_saved'] is None

def test_pilot_api(monkeypatch,tmp_path):
 from sentinel import api
 r=Repository(str(tmp_path/'db'));monkeypatch.setattr(api,'repo',r);c=TestClient(api.app);h={'X-API-Key':api.settings.api_key};p='/evaluation/trials';data=dict(task_id='T01',mode='manual',seconds=15,outcome='correct')
 assert c.post(p,json=data).status_code==401
 assert c.post(p,headers=h,json={**data,'seconds':-1}).status_code==422
 assert c.post(p,headers=h,json=data).status_code==200
 assert c.post(p,headers=h,json={**data,'mode':'sentinel','seconds':10}).status_code==200
 assert c.get(p,headers=h).json()['summary']['pairs']==1
