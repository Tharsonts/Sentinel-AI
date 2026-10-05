from types import SimpleNamespace
from pathlib import Path
import numpy as np
from sentinel.vision.detector import YoloTracker
def test_low_score_input_and_strict_new_track_threshold(tmp_path):
 # Inspect orchestration without asserting fake detector accuracy.
 class Values:
  def cpu(self):return self
  def tolist(self):return []
 class Model:
  def __init__(self):self.predictor=SimpleNamespace(trackers=[SimpleNamespace(args=SimpleNamespace())]);self.calls=[]
  def track(self,frame,**kwargs):self.calls.append(kwargs);return [SimpleNamespace(boxes=None)]
 tracker=YoloTracker.__new__(YoloTracker);tracker.model=Model();tracker.settings=SimpleNamespace(device='0');tracker.options=dict(quality='detail',confidence=.45,scope='objects');tracker.pose=None;tracker.configured_confidence=None;tracker.tracker_config=tmp_path/'tracker.yaml'
 tracker.overlay=SimpleNamespace(draw=lambda image,rows,now:image)
 tracker.process(np.zeros((80,80,3),np.uint8))
 assert tracker.model.calls[0]['conf']==.1
 assert 'new_track_thresh: 0.45' in tracker.tracker_config.read_text()
 assert 'fuse_score: false' in tracker.tracker_config.read_text()
 tracker.options['confidence']=.6;tracker.process(np.zeros((80,80,3),np.uint8))
 assert tracker.model.predictor.trackers[0].args.new_track_thresh==.6
 tracker.close();assert not tracker.tracker_config.exists()
