from types import SimpleNamespace
import numpy as np
from ultralytics.engine.results import Boxes
from sentinel.vision.detector import YoloTracker

class Model:
    def __init__(self,values):self.values=values;self.calls=[]
    def predict(self,frame,**kwargs):
        self.calls.append(kwargs)
        return [SimpleNamespace(boxes=Boxes(np.asarray(self.values,dtype=np.float32).reshape(-1,6),frame.shape[:2]),names={0:'person',2:'car'})]

def make_tracker():
    tracker=YoloTracker.__new__(YoloTracker)
    tracker.settings=SimpleNamespace(device='cpu',person_specialist_threshold=.75)
    tracker.options=dict(scope='person',quality='detail')
    tracker.model=Model([[10,10,40,70,.8,0]])
    tracker.specialist=Model([[50,10,80,70,.9,0]])
    tracker.fusion_tracker=None
    return tracker

def test_specialist_people_enter_same_tracker_and_keep_ids():
    tracker=make_tracker();frame=np.zeros((100,100,3),np.uint8)
    first=tracker._process_fused(frame,.45).boxes
    second=tracker._process_fused(frame,.45).boxes
    assert len(first)==len(second)==2
    assert first.id.tolist()==second.id.tolist()
    assert first.cls.tolist()==[0,0]

def test_other_scopes_keep_generic_classes_without_specialist():
    tracker=make_tracker();tracker.options['scope']='objects'
    tracker.model=Model([[10,10,40,70,.8,2]])
    result=tracker._process_fused(np.zeros((100,100,3),np.uint8),.45)
    assert result.boxes.cls.tolist()==[2]
    assert tracker.specialist.calls==[]

def test_empty_fusion_is_valid_tracker_input():
    tracker=make_tracker();tracker.model=Model([]);tracker.specialist=Model([])
    assert len(tracker._process_fused(np.zeros((100,100,3),np.uint8),.45).boxes)==0
