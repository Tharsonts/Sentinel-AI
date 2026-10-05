from sentinel.events.engine import EventEngine,Zone,Detection
def engine():return EventEngine([Zone(id='z',name='z',polygon=[(0,0),(.5,0),(.5,1),(0,1)],dwell_seconds=1)],'C','S',confirmation_seconds=.4)
def d(x=20,confidence=.8):return Detection(1,'person',confidence,(x-5,10,x+5,50))
def test_border_jitter_does_not_emit_entry_or_exit():
 e=engine()
 for t,x in [(0,20),(.1,80),(.2,20),(.3,80)]:assert not e.update([d(x)],100,100,t)
 assert not e.active
 assert not e.update([d()],100,100,1)
 assert e.update([d()],100,100,1.4)[0]['event_type']=='zone_enter'
 assert not e.update([d(80)],100,100,1.5)
 assert not e.update([d()],100,100,1.6)
 assert e.active
def test_confirmation_preserves_first_observation_duration():
 e=engine();e.update([d()],100,100,10);entry=e.update([d()],100,100,10.5)[0]
 assert entry['metadata']['confirmation_seconds']==.4
 assert e.update([d()],100,100,11)[0]['duration']==1
 assert not e.update([d(80)],100,100,11.1)
 assert e.update([d(80)],100,100,11.6)[0]['event_type']=='zone_exit'
def test_missing_frame_cannot_confirm_exit():
 e=engine();e.update([d()],100,100,0);e.update([d()],100,100,.5)
 e.update([d(80)],100,100,.6);assert not e.update([],100,100,.8)
 assert not e.update([d(80)],100,100,1)
 assert e.update([],100,100,3)[0]['event_type']=='track_lost'
def test_weak_recovery_does_not_start_presence_or_confirm_exit():
 e=engine();e.min_entry_confidence=.45
 assert not e.update([d(confidence=.2)],100,100,0)
 assert not e.update([d(confidence=.2)],100,100,1)
 e.update([d()],100,100,2);e.update([d()],100,100,2.5)
 assert not e.update([d(80,.2)],100,100,2.6)
 assert not e.update([d(80,.2)],100,100,3.1)
 assert e.active

def test_weak_gap_restarts_exit_confirmation():
 e=engine();e.min_entry_confidence=.45
 e.update([d()],100,100,0);e.update([d()],100,100,.5)
 e.update([d(80)],100,100,.6);e.update([d(80,.2)],100,100,.9)
 assert not e.update([d(80)],100,100,1.1)
 assert e.update([d(80)],100,100,1.6)[0]['event_type']=='zone_exit'
