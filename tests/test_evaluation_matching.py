import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('evaluation',Path(__file__).parents[1]/'scripts/evaluate_detection.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
def test_one_truth_cannot_match_two_boxes_or_wrong_class():
 truth=[('person',[0,0,10,10])]
 preds=[('person',[0,0,10,10],.9),('person',[0,0,10,10],.8),('car',[0,0,10,10],.7)]
 assert module.match(preds,truth)==dict(tp=1,fp=2,fn=0)
def test_missed_box_and_ignored_annotation_are_not_hidden():
 assert module.match([], [('person',[0,0,10,10])])==dict(tp=0,fp=0,fn=1)
 assert module.match([('person',[0,0,10,10],.9)],[],[('person',[0,0,10,10])])==dict(tp=0,fp=0,fn=0)
