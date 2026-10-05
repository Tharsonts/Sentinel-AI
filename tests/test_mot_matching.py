from sentinel.vision.evaluation import match_pedestrians

def test_targets_have_priority_over_ignore_regions():
 c,p=match_pedestrians([([0,0,10,10],.9)],[[0,0,10,10]],[[0,0,100,100]])
 assert c==dict(tp=1,fp=0,fn=0,ignored=0)

def test_ignore_uses_prediction_area_not_iou():
 c,p=match_pedestrians([([0,0,10,10],.9)],[],[[0,0,100,100]])
 assert c['ignored']==1 and c['fp']==0

def test_duplicate_predictions_cannot_match_same_person_twice():
 c,p=match_pedestrians([([0,0,10,10],.9),([0,0,10,10],.8)],[[0,0,10,10]],[])
 assert c['tp']==1 and c['fp']==1

def test_missing_target_is_counted():
 c,p=match_pedestrians([],[[0,0,10,10]],[]);assert c['fn']==1
