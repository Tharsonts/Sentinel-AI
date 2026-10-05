import numpy as np
from sentinel.vision.overlay import TrackOverlay,SCOPES,QUALITIES
from sentinel.vision.overlay import hand_candidates

def row(tid,kind,box):return dict(track_id=tid,object_type=kind,confidence=.8,box=list(box))

def test_movement_time_spacing_jitter_and_true_coordinates():
    overlay=TrackOverlay();frame=np.zeros((200,200,3),np.uint8)
    rows=[row(1,'person',(10,10,60,100))];overlay.draw(frame,rows,0)
    rows=[row(1,'person',(11,10,61,100))];overlay.draw(frame,rows,1)
    assert rows[0]['motion']=='pouca variacao'
    assert rows[0]['box']==[11,10,61,100] # events use measured boxes
    rows=[row(1,'person',(60,10,110,100))];overlay.draw(frame,rows,2)
    assert rows[0]['motion']=='em movimento'
    overlay.draw(frame,[],5);assert not overlay.history and not overlay.smoothed

def test_portable_proximity_is_not_hand_confirmation():
    overlay=TrackOverlay();rows=[row(1,'person',(20,10,100,190)),row(2,'cell phone',(50,80,65,100)),row(3,'bottle',(140,80,160,110))]
    overlay.draw(np.zeros((200,200,3),np.uint8),rows,0)
    assert rows[1]['near_person_ids']==[1] and rows[2]['near_person_ids']==[]
    assert 'in_hand' not in rows[1]

def test_untracked_box_is_visible_without_invented_id():
    rows=[row(None,'cup',(5,20,30,60))];overlay=TrackOverlay();image=overlay.draw(np.zeros((100,100,3),np.uint8),rows,0)
    assert image.any() and not overlay.history and rows[0]['track_id'] is None
    assert 67 in SCOPES['objects'] and 43 in SCOPES['objects'] and SCOPES['all'] is None
    assert QUALITIES['detail']==1280
    assert 15 not in SCOPES['objects'] and 16 not in SCOPES['objects']

def test_wrist_evidence_requires_visible_keypoint_and_is_not_held_claim():
    person=row(1,'person',(20,10,100,190));person['keypoints']=[[0,0,0] for _ in range(17)]
    item=row(2,'cell phone',(50,80,65,100))
    person['keypoints'][9]=[55,90,.49]
    assert hand_candidates(item,[person])==[]
    person['keypoints'][9]=[55,90,.9]
    assert hand_candidates(item,[person])==[{'person_id':1,'wrist':'esquerdo'}]
    person['keypoints'][9]=[120,90,.9]
    assert hand_candidates(item,[person])==[]

def test_options_authenticated_validated_and_same_session(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from sentinel import api
    monkeypatch.setattr(api.settings,'detection_profile_path',str(tmp_path/'detection.json'))
    monkeypatch.setattr(api.pipeline,'state',dict(status='running',session_id='unchanged',observations=[{'old':True}]))
    from types import SimpleNamespace
    monkeypatch.setattr(api.pipeline,'tracker',SimpleNamespace(options={}))
    monkeypatch.setattr(api.pipeline,'detection_options',dict(scope='objects',quality='balanced',confidence=.3))
    client=TestClient(api.app);headers={'X-API-Key':api.settings.api_key}
    assert client.get('/detection/options').status_code==401
    assert client.put('/detection/options',headers=headers,json={'scope':'magic'}).status_code==422
    assert client.put('/detection/options',headers=headers,json={'confidence':.01}).status_code==422
    response=client.put('/detection/options',headers=headers,json={'scope':'all','quality':'detail','confidence':.45})
    assert response.status_code==200 and response.json()['category_counts']['all']==80
    assert api.pipeline.state['session_id']=='unchanged' and api.pipeline.state['status']=='running'
    assert api.pipeline.tracker.options['quality']=='detail'
    assert (tmp_path/'detection.json').is_file()

def test_person_scope_api_and_categories(monkeypatch):
 from sentinel import api
 from fastapi.testclient import TestClient
 from sentinel.vision.overlay import SCOPES
 assert SCOPES['person']==[0]
 assert api.DetectionOptions(scope='person').scope=='person'
 monkeypatch.setattr(api.pipeline,'detection_options',dict(scope='person',quality='detail',confidence=.45))
 c=TestClient(api.app);h={'X-API-Key':api.settings.api_key}
 data=c.get('/detection/options',headers=h).json()
 assert data['category_counts']['person']==1 and data['options']['scope']=='person'
