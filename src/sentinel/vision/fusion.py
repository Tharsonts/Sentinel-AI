"""Conservative specialist supplementation: retain strong general detections."""
from sentinel.vision.overlay import box_iou

def supplement_people(base,specialist,extra_threshold,base_threshold=.45,overlap=.3):
 result=[(list(box),float(score)) for box,score in base]
 for box,score in sorted(specialist,key=lambda x:x[1],reverse=True):
  if score<extra_threshold:continue
  if any(s>=base_threshold and box_iou(box,b)>=overlap for b,s in result):continue
  result=[(b,s) for b,s in result if s>=base_threshold or box_iou(box,b)<overlap]
  result.append((list(box),float(score)))
 return result
