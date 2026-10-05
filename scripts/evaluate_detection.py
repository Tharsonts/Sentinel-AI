"""Evaluate fixed COCO-style labels without changing model weights or thresholds."""
import argparse,json,time
from pathlib import Path
from collections import defaultdict
import cv2,numpy as np
from ultralytics import YOLO
from sentinel.vision.overlay import SCOPES,box_iou

def match(predictions,truth,ignored=(),iou=.5):
    used=set();tp=fp=0
    for kind,box,score in sorted(predictions,key=lambda p:p[2],reverse=True):
        candidates=[(box_iou(box,b),i) for i,(cls,b) in enumerate(truth) if cls==kind and i not in used]
        overlap,index=max(candidates,default=(0,-1))
        if overlap>=iou:used.add(index);tp+=1
        elif any(cls==kind and box_iou(box,b)>=iou for cls,b in ignored):continue
        else:fp+=1
    return dict(tp=tp,fp=fp,fn=len(truth)-len(used))

def metrics(counts):
    p=counts['tp']/max(1,counts['tp']+counts['fp']);r=counts['tp']/max(1,counts['tp']+counts['fn'])
    return dict(**counts,precision=p,recall=r,f1=2*p*r/max(1e-9,p+r))

def main():
    args=argparse.ArgumentParser();args.add_argument('--manifest',required=True);args.add_argument('--images',required=True);args.add_argument('--output',required=True);args.add_argument('--models',nargs='+',default=['models/yolo11s.pt','models/yolo26s.pt']);opts=args.parse_args()
    data=json.loads(Path(opts.manifest).read_text());by_image=defaultdict(list)
    for a in data['annotations']:by_image[a['image_id']].append(a)
    names={c['id']:c['name'] for c in data['categories']};results=[]
    for filename in opts.models:
        model=YOLO(filename);scope={model.names[i] for i in SCOPES['objects']};totals=dict(tp=0,fp=0,fn=0);per_class={name:dict(tp=0,fp=0,fn=0) for name in sorted(scope)};times=[]
        model.predict(np.zeros((640,640,3),np.uint8),device=0,imgsz=1280,verbose=False)
        for image in data['images']:
            frame=cv2.imread(str(Path(opts.images)/image['file_name']));assert frame is not None,image['file_name']
            truth=[];ignored=[]
            for a in by_image[image['id']]:
                kind=names[a['category_id']]
                if kind not in scope:continue
                x,y,w,h=a['bbox'];(ignored if a.get('iscrowd') else truth).append((kind,[x,y,x+w,y+h]))
            begin=time.perf_counter();r=model.predict(frame,conf=.45,imgsz=1280,classes=SCOPES['objects'],device=0,verbose=False)[0];times.append((time.perf_counter()-begin)*1000)
            preds=[(r.names[int(cls)],box,float(score)) for cls,box,score in zip(r.boxes.cls.cpu().tolist(),r.boxes.xyxy.cpu().tolist(),r.boxes.conf.cpu().tolist())]
            for name in scope:
                counts=match([p for p in preds if p[0]==name],[p for p in truth if p[0]==name],[p for p in ignored if p[0]==name])
                for key in counts:totals[key]+=counts[key];per_class[name][key]+=counts[key]
        result=dict(model=Path(filename).name,images=len(data['images']),iou=.5,confidence=.45,imgsz=1280,metrics=metrics(totals),per_class={k:metrics(v) for k,v in per_class.items()},mean_ms=float(np.mean(times)),selection=data.get('selection'),limitations='Small fixed COCO validation subset; not incident accuracy, not mAP; crowd handling is a simplified IoU ignore rule.')
        results.append(result);print(json.dumps({k:v for k,v in result.items() if k!='per_class'}),flush=True)
    Path(opts.output).write_text(json.dumps(results,indent=2),encoding='utf-8')
if __name__=='__main__':main()
