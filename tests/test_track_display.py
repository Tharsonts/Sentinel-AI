import numpy as np
from sentinel.vision.overlay import TrackOverlay,track_color

def test_temporary_tracks_have_stable_distinct_colors():
    assert track_color(1)==track_color(1)
    assert track_color(1)!=track_color(2)

def test_missing_track_keeps_only_fading_trail_then_expires():
    overlay=TrackOverlay();frame=np.zeros((160,160,3),np.uint8)
    def row(x):return dict(track_id=2,object_type='car',box=[x,20,x+20,60],confidence=.9)
    overlay.draw(frame.copy(),[row(10)],0)
    overlay.draw(frame.copy(),[row(30)],1)
    lost=overlay.draw(frame.copy(),[],2)
    assert np.any(lost)
    assert not np.any(overlay.draw(frame.copy(),[],4.1))
