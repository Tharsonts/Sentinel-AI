"""MOT-style detection matching: target-first, ignore by intersection/prediction area."""
from sentinel.vision.overlay import box_iou

def match_pedestrians(predictions,targets,ignored,threshold=.5):
 used=set();tp=fp=ignored_count=0;pairs=[]
 for box,score in sorted(predictions,key=lambda p:p[1],reverse=True):
  candidates=[(box_iou(box,b),i) for i,b in enumerate(targets) if i not in used]
  overlap,index=max(candidates,default=(0,-1))
  if overlap>=threshold:used.add(index);tp+=1;pairs.append((index,box,score));continue
  area=max(0,box[2]-box[0])*max(0,box[3]-box[1])
  suppress=False
  for b in ignored:
   inter=max(0,min(box[2],b[2])-max(box[0],b[0]))*max(0,min(box[3],b[3])-max(box[1],b[1]))
   if area and inter/area>=.5:suppress=True;break
  if suppress:ignored_count+=1
  else:fp+=1
 return dict(tp=tp,fp=fp,fn=len(targets)-tp,ignored=ignored_count),pairs
