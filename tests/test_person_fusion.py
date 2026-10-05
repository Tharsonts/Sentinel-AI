from sentinel.vision.fusion import supplement_people

def test_specialist_cannot_replace_strong_general_box():
 base=[([0,0,10,10],.5)];assert supplement_people(base,[([0,0,11,11],.9)],.75)==base

def test_unmatched_low_specialist_score_is_rejected():
 assert supplement_people([], [([0,0,10,10],.7)],.75)==[]

def test_high_specialist_can_recover_weak_general_detection():
 out=supplement_people([([0,0,10,10],.2)],[([0,0,11,11],.8)],.75)
 assert out==[([0,0,11,11],.8)]

def test_supplementation_does_not_drop_existing_strong_predictions():
 base=[([0,0,10,10],.5)];out=supplement_people(base,[([50,50,60,60],.9)],.75)
 assert out[0]==base[0] and len(out)==2
