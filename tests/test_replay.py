from sentinel.storage.repository import Repository
from fastapi.testclient import TestClient

def test_replay_orders_video_time_and_isolates_sessions(tmp_path):
    r=Repository(str(tmp_path/'replay.db'))
    r.replay_save('A',2,640,480,[{'box':[1,2,3,4]}],[])
    r.replay_save('B',1,320,240,[],[])
    r.replay_save('A',1,640,480,[],[])
    first=r.replay('A',limit=1)
    assert first['has_more'] and first['items'][0]['offset_seconds']==1
    assert r.replay('A',offset=1,limit=1)['items'][0]['offset_seconds']==2
    assert r.replay('B')['items'][0]['width']==320

def test_annotations_do_not_replace_raw_images_for_ai(tmp_path):
    r=Repository(str(tmp_path/'replay.db'))
    r.visual_save('frame','A','CAM','2026-10-04T00:00:00Z',b'raw',offset_seconds=3)
    assert r.visual_processed_image('frame') is None
    r.visual_annotate('frame',b'annotated')
    assert r.visual_image('frame')==b'raw'
    assert r.visual_processed_image('frame')==b'annotated'

def test_replay_and_processed_frame_api_require_auth(monkeypatch,tmp_path):
    from sentinel import api
    r=Repository(str(tmp_path/'replay.db'));monkeypatch.setattr(api,'repo',r)
    r.register_session('A','CAM','file','demo','2026-10-04T00:00:00Z')
    r.replay_save('A',0,640,480,[],[])
    r.visual_save('frame','A','CAM','2026-10-04T00:00:00Z',b'raw',offset_seconds=0)
    r.visual_annotate('frame',b'annotated')
    c=TestClient(api.app);headers={'X-API-Key':api.settings.api_key}
    assert c.get('/sessions/A/replay').status_code==401
    assert c.get('/sessions/A/replay',headers=headers).json()['items'][0]['width']==640
    assert c.get('/sessions/missing/replay',headers=headers).status_code==404
    assert c.get('/visual/frames/frame?processed=true',headers=headers).content==b'annotated'
    assert c.get('/visual/frames/frame',headers=headers).content==b'raw'
