import io,json
from datetime import datetime,timezone,timedelta
from types import SimpleNamespace
import numpy as np
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from sentinel.events.engine import EventEngine,Zone,Detection
from sentinel.storage.repository import Repository
from sentinel.pipeline import Pipeline
from sentinel.search import interpret

def event(camera='A',kind='zone_enter',duration=0,t=100):
    engine=EventEngine([Zone(id='Z',name='Z',polygon=[(0,0),(1,0),(1,1),(0,1)])],camera,'SESSION')
    return engine.event(kind,Detection(1,'person',.9,(10,10,30,30)),engine.zones[0],t,duration)

@pytest.fixture
def client(tmp_path,monkeypatch):
    import sentinel.api as api
    repository=Repository(str(tmp_path/'api.sqlite'))
    monkeypatch.setattr(api,'repo',repository)
    monkeypatch.setattr(api,'pipeline',SimpleNamespace(snapshot=lambda:{'status':'idle'},zones=lambda:[],stop=lambda:{}))
    with TestClient(api.app) as c:yield c,repository,{'X-API-Key':api.settings.api_key}

def bounds(**extra):
    return dict(since=datetime.fromtimestamp(99,timezone.utc).isoformat(),until=datetime.fromtimestamp(120,timezone.utc).isoformat(),**extra)

def test_search_filters_total_pagination_and_exact_boundaries(tmp_path):
    r=Repository(str(tmp_path/'db'))
    r.save([event(t=99),event(t=100),event(t=101),event(camera='B',t=102),event(kind='zone_dwell',duration=21,t=110),event(t=120)])
    start=datetime.fromtimestamp(100,timezone.utc).isoformat();end=datetime.fromtimestamp(120,timezone.utc).isoformat()
    first=r.search(since=start,until=end,camera='A',limit=1)
    second=r.search(since=start,until=end,camera='A',limit=1,offset=1)
    assert first['total']==3 and first['has_more'] and first['items'][0]['id']!=second['items'][0]['id']
    durations=r.search(since=start,until=end,camera='A',zone='Z',object_type='person',min_duration=20)
    assert durations['total']==1 and durations['items'][0]['duration']==21
    assert r.search(since=start,until=end,camera="A' OR 1=1 --")['total']==0
    assert sum(x['count'] for x in r.search_stats(since=start,until=end,camera='A'))==3

def test_evidence_is_persisted_with_event_and_old_events_remain_empty(tmp_path):
    r=Repository(str(tmp_path/'db'));old=event(t=100);new=event(t=101)
    encoded=io.BytesIO();Image.new('RGB',(64,48),'green').save(encoded,format='JPEG')
    r.save([old]);r.save([new],encoded.getvalue());reopened=Repository(r.path)
    assert reopened.evidence(old['id']) is None
    assert reopened.evidence(new['id'])==encoded.getvalue()
    result=reopened.search(**bounds())
    assert result['items'][0]['evidence_available'] and not result['items'][1]['evidence_available']
    assert result['items'][0]['evidence_captured_at']==new['timestamp']

def test_evidence_and_event_transaction_roll_back_together(tmp_path):
    r=Repository(str(tmp_path/'db'));duplicate=event();r.save([duplicate]);new=event(t=101)
    with pytest.raises(Exception):r.save([new,duplicate],b'jpeg')
    assert r.get(new['id']) is None and r.evidence(new['id']) is None

def test_pipeline_saves_annotated_frame_but_never_invents_timeout_evidence(tmp_path):
    config=tmp_path/'zones.json';config.write_text(json.dumps([dict(id='Z',name='Z',polygon=[[0,0],[1,0],[1,1],[0,1]],dwell_seconds=3)]))
    repo=Repository(str(tmp_path/'db'));p=Pipeline(SimpleNamespace(max_frame_dimension=1280,zones_path=str(config)),repo)
    p.engine=EventEngine(p.zones(),'TEST','SESSION',2)
    p.tracker=SimpleNamespace(process=lambda f:([Detection(1,'person',.9,(10,10,30,30))],f.copy()))
    p.process(np.zeros((100,100,3),np.uint8),100)
    for timestamp in (101,102,103,104):p.process(np.ones((100,100,3),np.uint8)*200,timestamp)
    rows=repo.query();assert len(rows)==2
    assert repo.evidence(rows[0]['id'])!=repo.evidence(rows[1]['id'])
    image=Image.open(io.BytesIO(repo.evidence(rows[0]['id'])));assert image.size==(100,100)
    assert np.array(image).std()>0 # zone annotation, not just the source image
    lost=p.engine.update([],100,100,107);repo.save(lost)
    assert lost[0]['event_type']=='track_lost' and repo.evidence(lost[0]['id']) is None

def test_search_api_auth_validation_and_evidence(client):
    c,r,h=client;e=event();r.save([e],b'jpeg')
    assert c.post('/search',json=bounds()).status_code==401
    assert c.get('/events/'+e['id']+'/evidence').status_code==401
    result=c.post('/search',headers=h,json=bounds(query='entradas de pessoas',camera='A')).json()
    assert result['total']==1 and result['filters']['object_type']=='person'
    image=c.get('/events/'+e['id']+'/evidence',headers=h)
    assert image.content==b'jpeg' and image.headers['cache-control']=='no-store'
    assert c.get('/events/missing/evidence',headers=h).status_code==404
    assert c.post('/search',headers=h,json=bounds(min_duration=-1)).status_code==422
    assert c.post('/search',headers=h,json=bounds(query='entradas de pessoas',object_type='car')).status_code==400
    assert c.post('/search',headers=h,json=bounds(query='pessoas suspeitas')).status_code==400
    assert c.post('/search',headers=h,json={'since':'2026-10-02T00:00:00','until':'2026-10-03T00:00:00'}).status_code==400
    assert c.post('/search',headers=h,json={'since':'2026-10-03T00:00:00Z','until':'2026-10-02T00:00:00Z'}).status_code==400

def test_chat_and_report_have_same_camera_and_filters(client):
    c,r,h=client;r.save([event(camera='A',kind='zone_dwell',duration=21,t=105),event(camera='B',t=106),event(camera='A',t=107)])
    request={**bounds(camera='A',query='permanência de pessoas',min_duration=20),'use_llm':False}
    result=c.post('/chat',headers=h,json=request).json()
    assert result['context']['total']==1 and result['context']['counts'][0]['count']==1
    assert all(e['camera']=='A' and e['event_type']=='zone_dwell' for e in result['context']['events'])
    text=c.post('/search/report',headers=h,json=request).text
    assert 'Total de eventos: 1' in text and '| B |' not in text
    assert c.post('/chat',headers=h,json={'since':request['since'],'use_llm':False}).status_code==400

def test_llm_receives_only_selected_events_and_no_image_data(client,monkeypatch):
    import sentinel.api as api
    captured=[]
    class Provider:
        def __init__(self,s):pass
        async def chat(self,messages):captured.append(messages);return 'Resumo de teste'
    monkeypatch.setattr(api,'OllamaProvider',Provider);monkeypatch.setattr(api.settings,'llm_provider','ollama')
    c,r,h=client;a=event(camera='A',kind='presence_ended');a['metadata']={'reason':'source_ended','exit_confirmed':False};b=event(camera='B');r.save([a],b'jpeg');r.save([b])
    response=c.post('/chat',headers=h,json={**bounds(camera='A'),'use_llm':True})
    assert response.status_code==200
    ctx=json.loads(captured[0][1]['content'])['recorded_events']
    assert [e['id'] for e in ctx['events']]==[a['id']] and b['id'] not in captured[0][1]['content']
    assert 'jpeg' not in captured[0][1]['content']
    assert ctx['events'][0]['metadata']=={'reason':'source_ended','exit_confirmed':False}
    assert ctx['detail_sessions']==[a['session_id']]
    assert 'sem acesso ao vídeo' in response.json()['answer']

def test_large_llm_context_is_bounded_without_lying_about_total(client,monkeypatch):
    import sentinel.api as api
    captured=[]
    class Provider:
        def __init__(self,s):pass
        async def chat(self,messages):captured.append(json.loads(messages[1]['content'])['recorded_events']);return 'Resumo'
    monkeypatch.setattr(api,'OllamaProvider',Provider);monkeypatch.setattr(api.settings,'llm_provider','ollama')
    c,r,h=client;r.save([event(t=100+i/100) for i in range(35)])
    result=c.post('/chat',headers=h,json={**bounds(),'use_llm':True}).json()
    assert captured[0]['total']==35 and len(captured[0]['events'])==24 and captured[0]['truncated']
    assert result['llm_events_used']==24 and 'últimos 24 eventos' in result['answer']

def test_timezone_offsets_are_normalized_and_end_is_exclusive(client):
    c,r,h=client;e=event(t=datetime(2026,10,3,2,30,tzinfo=timezone.utc).timestamp());r.save([e])
    response=c.post('/search',headers=h,json={'since':'2026-10-02T00:00:00-03:00','until':'2026-10-03T00:00:00-03:00'}).json()
    assert response['total']==1 and response['filters']['until']=='2026-10-03T03:00:00+00:00'

@pytest.mark.parametrize('text',['pessoas suspeitas','pessoas de camisa vermelha','entradas de pessoas ontem','entradas e saídas de pessoas','pessoas e carros'])
def test_unsupported_search_is_not_silently_broadened(text):
    with pytest.raises(ValueError):interpret(text)

def test_assets_are_allowlisted(client):
    c,_,_=client
    assert c.get('/assets/dashboard.js').status_code==200
    assert c.get('/assets/.env').status_code==404

def test_push_identity_is_checked_inside_processing_lock(tmp_path):
    repo=Repository(str(tmp_path/'db'));p=Pipeline(SimpleNamespace(),repo)
    p.state.update(status='running',kind='push',camera='A',session_id='new')
    frame=np.zeros((10,10,3),np.uint8)
    with pytest.raises(ValueError,match='Outra câmera'):p.process(frame,expected_camera='B',require_push=True)
    with pytest.raises(ValueError,match='sessão mudou'):p.process(frame,expected_camera='A',expected_session='old',require_push=True)
    p.state['status']='stopping'
    with pytest.raises(ValueError,match='tipo push'):p.process(frame,expected_camera='A',require_push=True)


def test_session_filter_is_shared_by_search_chat_counts_and_report(client,monkeypatch):
    import sentinel.api as api
    captured=[]
    class Provider:
        def __init__(self,s):pass
        async def chat(self,messages):captured.append(json.loads(messages[1]['content'])['recorded_events']);return 'Resumo'
    monkeypatch.setattr(api,'OllamaProvider',Provider);monkeypatch.setattr(api.settings,'llm_provider','ollama')
    c,r,h=client;a=event(t=100);b=event(t=101);b['session_id']='OTHER';r.save([a,b])
    query=bounds(camera='A',session_id='SESSION')
    result=c.post('/search',headers=h,json=query).json()
    assert result['total']==1 and result['items'][0]['id']==a['id']
    response=c.post('/chat',headers=h,json={**query,'use_llm':True}).json()
    assert response['context']['total']==1 and sum(s['count'] for s in response['context']['counts'])==1
    assert captured[0]['detail_sessions']==['SESSION'] and b['id'] not in str(captured)
    report=c.post('/search/report',headers=h,json=query).text
    assert a['id'] in report and b['id'] not in report
    assert c.post('/search',headers=h,json=bounds(session_id="' OR 1=1 --")).json()['total']==0
    assert {s['session_id'] for s in c.get('/search/catalog',headers=h).json()['sessions']}=={'SESSION','OTHER'}


def test_saved_camera_profile_does_not_expose_credentials(client,monkeypatch,tmp_path):
    import sentinel.api as api
    monkeypatch.setattr(api.settings,'camera_profile_path',str(tmp_path/'camera.local.json'))
    c,r,h=client
    assert c.post('/camera/profile',json={'kind':'rtsp','source':'rtsp://u:private-test@127.0.0.1/camera'}).status_code==401
    response=c.post('/camera/profile',headers=h,json={'kind':'rtsp','source':'rtsp://u:private-test@127.0.0.1/camera','camera':'IP01','auto_start':False})
    assert response.status_code==200
    public=c.get('/camera/profile',headers=h).json();assert public['saved'] and public['camera']=='IP01'
    assert 'private-test' not in str(public) and 'source' not in public
    assert c.post('/camera/profile',headers=h,json={'kind':'rtsp','source':'file:///etc/passwd'}).status_code==400
    assert c.post('/camera/profile',headers=h,json={'kind':'file','source':'video.mp4'}).status_code==422

def test_original_video_is_authenticated_range_capable_and_confined(client,monkeypatch,tmp_path):
    import sentinel.api as api
    c,r,h=client;media=tmp_path/'media';media.mkdir();(media/'clip.mp4').write_bytes(b'0123456789');(tmp_path/'outside.mp4').write_bytes(b'private')
    monkeypatch.setattr(api.settings,'media_dir',str(media))
    r.register_session('PLAY','C','file','clip','2026-10-03T03:00:00+00:00','clip.mp4')
    r.register_session('ESCAPE','C','file','outside','2026-10-03T03:00:00+00:00','../outside.mp4')
    assert c.get('/sessions/PLAY/video').status_code==401
    response=c.get('/sessions/PLAY/video',headers={**h,'Range':'bytes=2-4'})
    assert response.status_code==206 and response.content==b'234'
    assert c.get('/sessions/ESCAPE/video',headers=h).status_code==404
    assert c.get('/visual/frames/anything').status_code==401
