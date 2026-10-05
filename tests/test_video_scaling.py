from types import SimpleNamespace
import cv2
import numpy as np
import pytest
from sentinel.pipeline import Pipeline
from sentinel.events.engine import EventEngine, Zone, Detection
from sentinel.storage.repository import Repository

@pytest.mark.parametrize('shape,expected', [((2160,3840),(720,1280)),((1920,1080),(1280,720)),((480,640),(480,640))])
def test_large_frames_keep_proportion_zone_coordinates_and_evidence(tmp_path,shape,expected):
    settings=SimpleNamespace(max_frame_dimension=1280)
    repository=Repository(str(tmp_path/'video.db'))
    pipeline=Pipeline(settings,repository)
    class Tracker:
        def process(self,frame):
            h,w=frame.shape[:2]
            assert (h,w)==expected
            return [Detection(1,'person',.9,(w*.4,h*.2,w*.6,h*.7))],frame.copy()
    pipeline.tracker=Tracker()
    pipeline.engine=EventEngine([Zone(id='middle',name='Middle',polygon=[(.3,0),(.7,0),(.7,1),(.3,1)])],'CAM','SESSION')
    result=pipeline.process(np.zeros((*shape,3),dtype=np.uint8),100)
    assert result['events'][0]['event_type']=='zone_enter'
    image=cv2.imdecode(np.frombuffer(pipeline.jpg,dtype=np.uint8),cv2.IMREAD_COLOR)
    assert image.shape[:2]==expected
    assert repository.get(result['events'][0]['id']) is not None
