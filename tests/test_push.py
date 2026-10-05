import time,json
from types import SimpleNamespace
import numpy as np
from sentinel.pipeline import Pipeline
from sentinel.events.engine import Detection
from sentinel.storage.repository import Repository
class Stub:
    def __init__(self,s):pass
    def process(self,frame):return [Detection(1,"person",.9,(20,20,50,50))],frame.copy()
def test_push_timeout_records_uncertainty(tmp_path):
    zones=tmp_path/'zones.json';zones.write_text(json.dumps([dict(id='Z',name='Z',polygon=[[0,0],[1,0],[1,1],[0,1]],dwell_seconds=.1)]))
    # This test exercises timeout semantics independently of entry debounce.
    s=SimpleNamespace(max_frame_dimension=1280,zones_path=str(zones),lost_timeout=.1,zone_confirmation_seconds=0)
    repo=Repository(str(tmp_path/'db.sqlite'));p=Pipeline(s,repo,Stub)
    p.start('push','','PUSH');deadline=time.time()+3
    while p.snapshot()['status']=='starting' and time.time()<deadline:time.sleep(.01)
    try:
        p.process(np.zeros((100,100,3),np.uint8));time.sleep(.8)
        events=repo.query();assert any(e['event_type']=='track_lost' for e in events)
        assert not any(e['event_type']=='zone_exit' for e in events)
        assert p.jpg is not None
    finally:p.stop()
