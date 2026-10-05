import json,time
from types import SimpleNamespace
import cv2,numpy as np,pytest
from sentinel.storage.repository import Repository
from sentinel.visual import VisualService

def test_clip_samples_exact_video_offsets_and_session(tmp_path):
 r=Repository(str(tmp_path/'db'));r.register_session('A','CAM','file','clip','2026-10-03T00:00:00Z')
 ok,jpeg=cv2.imencode('.jpg',np.zeros((40,40,3),np.uint8))
 for session in ['A','B']:
  for i in range(20):r.visual_save(session+str(i),session,'CAM',f'2026-10-03T00:00:{i:02d}Z',jpeg.tobytes(),offset_seconds=i)
 selected=r.visual_samples('A',start_seconds=5,end_seconds=17)
 assert [f['offset_seconds'] for f in selected]==list(range(5,17))
 assert all(f['session_id']=='A' for f in selected)

def test_clip_validation_and_result_metadata(tmp_path,monkeypatch):
 import sentinel.visual as module
 r=Repository(str(tmp_path/'db'));r.register_session('A','CAM','file','clip','2026-10-03T00:00:00Z')
 ok,jpeg=cv2.imencode('.jpg',np.zeros((40,40,3),np.uint8));r.visual_save('one','A','CAM','2026-10-03T00:00:05Z',jpeg.tobytes(),offset_seconds=5)
 class Provider:
  def __init__(self,s):pass
  async def vision(self,messages,schema):return json.dumps({'summary':'Cena','observations':[{'description':'Escuro','frame_labels':['F1']}],'uncertainty':'Sem áudio'})
 monkeypatch.setattr(module,'OllamaProvider',Provider)
 s=VisualService(SimpleNamespace(llm_provider='ollama',llm_model='test'),r)
 for start,end in [(None,5),(5,None),(-1,5),(5,5),(0,13)]:
  with pytest.raises(ValueError):s.submit('A',start_seconds=start,end_seconds=end)
 with pytest.raises(ValueError,match='não tem imagens'):s.submit('A',start_seconds=10,end_seconds=12)
 s.submit('A',start_seconds=4,end_seconds=7)
 deadline=time.monotonic()+2
 while r.visual_report('A')['status']!='ready' and time.monotonic()<deadline:time.sleep(.01)
 result=r.visual_report('A')['result'];assert result['selection']=={'start_seconds':4,'end_seconds':7}
 assert result['frames'][0]['offset_seconds']==5

def test_clip_not_allowed_for_live_source(tmp_path):
 r=Repository(str(tmp_path/'db'));r.register_session('A','CAM','push','live','2026-10-03T00:00:00Z')
 s=VisualService(SimpleNamespace(llm_provider='ollama',llm_model='test'),r)
 with pytest.raises(ValueError,match='gravados'):s.submit('A',start_seconds=0,end_seconds=5)

def test_clip_api_auth_and_nonfinite_offsets(monkeypatch):
 from sentinel import api
 from fastapi.testclient import TestClient
 calls=[]
 class Service:
  def submit(self,*args,**kwargs):calls.append(kwargs);return {'status':'queued'}
 monkeypatch.setattr(api,'visual',Service());c=TestClient(api.app)
 payload={'session_id':'A','start_seconds':1,'end_seconds':5}
 assert c.post('/visual/analyze',json=payload).status_code==401
 headers={'X-API-Key':api.settings.api_key}
 assert c.post('/visual/analyze',headers=headers,json=payload).status_code==200
 assert calls[0]['start_seconds']==1 and calls[0]['end_seconds']==5
 assert c.post('/visual/analyze',headers=headers,json={**payload,'start_seconds':'NaN'}).status_code==422
