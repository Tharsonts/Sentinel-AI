import pytest
from sentinel.events.engine import EventEngine,Zone,Detection

def make():
 e=EventEngine([Zone(id='R',name='Área restrita',polygon=[(0,0),(.5,0),(.5,1),(0,1)],classes=['person'],dwell_seconds=1)],'C','S',confirmation_seconds=.4);e.min_entry_confidence=.45;return e

def d(conf=.9,kind='person'):return Detection(1,kind,conf,(10,10,30,50))

def test_gap_never_becomes_dwell_or_continuous_entry():
 e=make();assert not e.update([d()],100,100,0)
 assert not e.update([d()],100,100,10)
 assert e.update([d()],100,100,10.4)[0]['event_type']=='zone_enter'
 result=e.update([d()],100,100,20)
 assert [x['event_type'] for x in result]==['track_lost']
 assert result[0]['metadata']['reason']=='observation_gap'

def test_weak_or_missing_intervals_do_not_count_toward_dwell():
 e=make();e.update([d()],100,100,0);e.update([d()],100,100,.4)
 assert not e.update([d(.2)],100,100,.8)
 assert not e.update([d()],100,100,1.2)
 assert not e.update([],100,100,1.4)
 assert not e.update([d()],100,100,1.6)
 result=e.update([d()],100,100,2.2)
 assert len(result)==1 and result[0]['event_type']=='zone_dwell'
 assert result[0]['metadata']['observed_seconds']==1

def test_empty_scene_and_wrong_category_emit_no_alerts():
 e=make()
 for i in range(100):assert not e.update([d(kind='car')] if i%2 else [],100,100,i*.1)

def test_backward_clock_is_rejected():
 import pytest
 e=make();e.update([],100,100,5)
 with pytest.raises(ValueError):e.update([],100,100,4)


def test_gap_event_cannot_receive_current_image(tmp_path):
 from sentinel.storage.repository import Repository
 e=make();e.update([d()],100,100,0);e.update([d()],100,100,.4)
 events=e.update([d()],100,100,10);r=Repository(str(tmp_path/'db'));r.save(events,b'current frame')
 assert r.evidence(events[0]['id']) is None


def test_heartbeats_cannot_make_returning_id_inherit_old_presence():
 e=make();e.update([d()],100,100,0);e.update([d()],100,100,.4)
 e.update([],100,100,1);e.update([],100,100,2)
 result=e.update([d()],100,100,2.5)
 assert [r['event_type'] for r in result]==['track_lost']
 assert not e.active
 assert e.update([d()],100,100,2.9)[0]['event_type']=='zone_enter'
 assert e.supported[(1,'R')]==pytest.approx(.4)
