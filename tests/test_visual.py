import base64,json,time
from types import SimpleNamespace
import cv2,numpy as np,pytest
from sentinel.visual import visual_messages,validated_result,VisualService
from sentinel.storage.repository import Repository
from sentinel.pipeline import Pipeline
from sentinel.events.engine import EventEngine,Zone

def frame(repository,id='one',session='A',t='2026-10-03T03:00:00+00:00'):
    ok,jpeg=cv2.imencode('.jpg',np.zeros((80,120,3),np.uint8));repository.visual_save(id,session,'CAM',t,jpeg.tobytes())

def test_sampling_is_ordered_scoped_and_sends_real_images(tmp_path):
    r=Repository(str(tmp_path/'db'))
    for i in range(10):frame(r,str(i),'A',f'2026-10-03T03:00:{i:02d}+00:00')
    frame(r,'other','B')
    selected=r.visual_samples('A',limit=6);assert len(selected)==6 and selected[0]['id']=='0' and selected[-1]['id']=='9'
    messages,schema=visual_messages(selected,r,'O que aparece?')
    assert len([m for m in messages if 'images' in m])==6
    assert 'other' not in str(selected)
    image=cv2.imdecode(np.frombuffer(base64.b64decode(messages[2]['images'][0]),np.uint8),cv2.IMREAD_COLOR)
    assert image.shape[:2]==(80,120)
    assert schema['properties']['observations']['items']['properties']['frame_labels']['items']['enum']==['F1','F2','F3','F4','F5','F6']

def test_unreceived_visual_reference_is_rejected(tmp_path):
    r=Repository(str(tmp_path/'db'));frame(r);frames=r.visual_samples('A')
    answer={'summary':'Cena','observations':[{'description':'Objeto','frame_labels':['F99']}],'uncertainty':'Limitado'}
    with pytest.raises(ValueError,match='não recebeu'):validated_result(json.dumps(answer),frames,'q','A','model',1)
    answer['observations'][0]['frame_labels']=['F1'];result=validated_result(json.dumps(answer),frames,'q','A','model',1)
    assert result['observations'][0]['frame_ids']==['one']

def test_empty_detector_still_stores_unannotated_visual_evidence(tmp_path):
    r=Repository(str(tmp_path/'db'));p=Pipeline(SimpleNamespace(max_frame_dimension=1280),r)
    p.engine=EventEngine([Zone(id='zone',name='zone',polygon=[(0,0),(1,0),(1,1),(0,1)])],'CAM','S')
    class Tracker:
        def process(self,image):image[:]=(0,0,255);return [],image
    p.tracker=Tracker();p.process(np.zeros((80,120,3),np.uint8),100);p.process(np.zeros((80,120,3),np.uint8),101)
    stored=r.visual_samples('S');assert len(stored)==1
    decoded=cv2.imdecode(np.frombuffer(r.visual_image(stored[0]['id']),np.uint8),cv2.IMREAD_COLOR)
    assert decoded.mean()<1 and not p.engine.active

def test_visual_queue_stores_validated_result_and_deduplicates(tmp_path,monkeypatch):
    import sentinel.visual as module
    r=Repository(str(tmp_path/'db'));frame(r)
    class Provider:
        def __init__(self,s):pass
        async def vision(self,messages,schema):return json.dumps({'summary':'Imagem escura','observations':[{'description':'Fundo escuro','frame_labels':['F1']}],'uncertainty':'Sem vídeo contínuo'})
    monkeypatch.setattr(module,'OllamaProvider',Provider)
    service=VisualService(SimpleNamespace(llm_provider='ollama',llm_model='test'),r);service.submit('A')
    deadline=time.time()+2
    while r.visual_report('A')['status']!='ready' and time.time()<deadline:time.sleep(.01)
    report=r.visual_report('A');assert report['status']=='ready' and report['result']['frames'][0]['id']=='one'
    assert service.submit('A')['updated_at']==report['updated_at']
    with pytest.raises(ValueError,match='não tem imagens'):service.submit('missing')

def test_registered_session_without_events_is_visible(tmp_path):
    r=Repository(str(tmp_path/'db'));r.register_session('S','C','file','clip.mp4','2026-10-03T03:00:00+00:00');frame(r,session='S')
    item=r.sessions()[0];assert item['count']==0 and item['visual_count']==1 and item['name']=='clip.mp4'


def test_retention_keeps_images_cited_by_the_current_report(tmp_path):
    r=Repository(str(tmp_path/'db'));frame(r,'old')
    r.visual_report_save('A','ready',{'frames':[{'id':'old'}]})
    for i in range(4):
        ok,jpeg=cv2.imencode('.jpg',np.zeros((40,40,3),np.uint8))
        r.visual_save(str(i),'A','CAM',f'2026-10-03T03:01:0{i}+00:00',jpeg.tobytes(),keep=2)
    assert r.visual_image('old') is not None and r.visual_image('0') is None
    assert {f['id'] for f in r.visual_samples('A')}=={'old','2','3'}

def test_rtsp_read_interruption_reopens_source(tmp_path,monkeypatch):
    import sentinel.pipeline as module
    zones=tmp_path/'zones.json';zones.write_text('[]')
    settings=SimpleNamespace(max_frame_dimension=1280,zones_path=str(zones),lost_timeout=2)
    instances=[]
    class Source:
        fps=25
        def __init__(self,source):self.index=len(instances);instances.append(self);self.closed=False
        def read(self):return (False,None) if self.index==0 else (True,np.zeros((80,120,3),np.uint8))
        def close(self):self.closed=True
    class Tracker:
        def __init__(self,s):pass
        def process(self,image):return [],image
    monkeypatch.setattr(module,'RTSPVideoSource',Source)
    p=Pipeline(settings,Repository(str(tmp_path/'db')),Tracker)
    real_wait=p.stop_flag.wait;monkeypatch.setattr(p.stop_flag,'wait',lambda seconds:real_wait(min(seconds,.01)))
    p.start('rtsp','rtsp://example.invalid/test','CAM')
    deadline=time.time()+2
    while p.snapshot().get('frames',0)<2 and time.time()<deadline:time.sleep(.01)
    state=p.stop();assert state['frames']>=2 and len(instances)>=2 and instances[0].closed
    assert state['error'] is None and not state.get('reconnecting',False)
