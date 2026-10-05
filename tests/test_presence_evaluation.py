import pytest
from sentinel.presence_evaluation import evaluate_events

def ref(events=None,**kwargs):
 return {'recordings':[dict(id='A',source_group='A_day1',split='test',reviewer='annotator',reference_origin='manual',reviewed_full_video=True,duration_seconds=3600,expected_events=events or [],**kwargs)]}
def truth(a=10,b=11):return dict(event_type='zone_enter',zone='R',window_seconds=[a,b],reference_seconds=a)
def pred(t=10,zone='R'):return dict(event_type='zone_enter',zone=zone,offset_seconds=t)

def test_empty_or_unreviewed_reference_cannot_pass():
 with pytest.raises(ValueError):evaluate_events({'recordings':[]},{})
 r=ref();r['recordings'][0]['reviewed_full_video']=False
 with pytest.raises(ValueError):evaluate_events(r,{'A':[]})

def test_duplicates_and_missed_events_count():
 r=evaluate_events(ref([truth(),truth(20,21)]),{'A':[pred(),pred(),pred(12)]})
 assert (r['tp'],r['fp'],r['fn'])==(1,2,1)
 assert r['precision']==1/3 and r['recall']==.5 and r['false_alerts_per_hour']==2
 assert not r['operational_approval']

def test_missing_recording_predictions_rejected():
 with pytest.raises(ValueError):evaluate_events(ref([truth()]),{})

def test_maximum_matching_prevents_greedy_undercount():
 r=evaluate_events(ref([truth(10,12),truth(10,10)]),{'A':[pred(10),pred(12)]})
 assert r['tp']==2 and r['fp']==r['fn']==0

def test_negative_scene_has_no_invented_recall():
 r=evaluate_events(ref(),{'A':[pred(zone='OTHER')]});assert r['recall'] is None and r['fp']==1

def test_overlap_ambiguity_not_counted_as_negative_time():
 r=evaluate_events(ref(unverifiable_intervals=[[0,100],[50,150]]),{'A':[pred(10)]})
 assert r['ignored_predictions']==1 and r['reviewed_hours']==3450/3600

def test_origin_cannot_leak_between_splits():
 r=ref();other={**r['recordings'][0],'id':'B','split':'train'};r['recordings'].append(other)
 with pytest.raises(ValueError):evaluate_events(r,{'A':[]})

def test_bad_timestamps_rejected():
 with pytest.raises(ValueError):evaluate_events(ref(),{'A':[pred(float('nan'))]})
