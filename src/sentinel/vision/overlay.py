"""Measured paths and display-only smoothing; no identity or hand inference."""
from collections import deque
import cv2
import numpy as np

SCOPES={'person':[0], 'traffic':[0,1,2,3,5,7], 'objects':[0,1,2,3,5,7,24,25,26,28,39,41,43,63,67,76], 'all':None}
QUALITIES={'fast':640,'balanced':960,'detail':1280}
LABELS={'person':'Pessoa','bicycle':'Bicicleta','car':'Carro','motorcycle':'Moto','bus':'Onibus','truck':'Caminhao','cat':'Gato','dog':'Cachorro','backpack':'Mochila','umbrella':'Guarda-chuva','handbag':'Bolsa','suitcase':'Mala','bottle':'Garrafa','cup':'Copo','knife':'Faca','laptop':'Notebook','cell phone':'Celular','scissors':'Tesoura'}
PORTABLE={'backpack','handbag','suitcase','bottle','cup','knife','laptop','cell phone','scissors','umbrella'}
LIMBS=[(5,6),(5,7),(7,9),(6,8),(8,10),(5,11),(6,12),(11,12),(11,13),(13,15),(12,14),(14,16)]

def hand_candidates(item,people):
    candidates=[];x1,y1,x2,y2=item['box']
    for person in people:
        if person['track_id'] is None:continue
        points=person.get('keypoints',[])
        if len(points)!=17:continue
        pad=max(6,(person['box'][2]-person['box'][0])*.08)
        for index,hand in [(9,'esquerdo'),(10,'direito')]:
            x,y,confidence=points[index]
            if confidence>=.5 and x1-pad<=x<=x2+pad and y1-pad<=y<=y2+pad:
                candidates.append({'person_id':person['track_id'],'wrist':hand})
    return candidates

def box_iou(a,b):
    intersection=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
    area=lambda c:max(0,c[2]-c[0])*max(0,c[3]-c[1])
    return intersection/max(1e-9,area(a)+area(b)-intersection)

class TrackOverlay:
    def __init__(self):self.history={};self.smoothed={}
    def draw(self,frame,rows,now):
        height,width=frame.shape[:2]
        self.history={k:v for k,v in self.history.items() if now-v[-1][0]<2}
        self.smoothed={k:v for k,v in self.smoothed.items() if k in self.history}
        people=[r for r in rows if r['object_type']=='person']
        for row in rows:
            box=np.asarray(row['box'],float);tid=row['track_id'];kind=row['object_type'];motion='sem historico';display=box
            if tid is not None:
                key=(tid,kind);history=self.history.setdefault(key,deque(maxlen=90));point=((box[0]+box[2])/2,box[3])
                if not history or now-history[-1][0]>=.08:history.append((now,*point))
                while history and now-history[0][0]>3:history.popleft()
                baseline=next((p for p in reversed(history) if now-p[0]>=.5),None)
                if baseline:
                    speed=np.hypot(point[0]-baseline[1],point[1]-baseline[2])/max(.001,now-baseline[0])/max(height,width)
                    motion='em movimento' if speed>.025 else 'pouca variacao'
                old=self.smoothed.get(key,box)
                display=.65*box+.35*old if box_iou(old,box)>.65 else box
                self.smoothed[key]=display
                if kind=='person' and len(history)>1:
                    pts=np.asarray([(int(p[1]),int(p[2])) for p in history],np.int32)
                    cv2.polylines(frame,[pts],False,(145,210,165),2,cv2.LINE_AA)
            row['motion']=motion if kind=='person' else None;nearby=[]
            if kind in PORTABLE:
                cx,cy=(box[0]+box[2])/2,(box[1]+box[3])/2
                for person in people:
                    px1,py1,px2,py2=person['box'];pad=(px2-px1)*.12
                    if px1-pad<=cx<=px2+pad and py1<=cy<=py2 and person['track_id'] is not None:nearby.append(person['track_id'])
            row['near_person_ids']=nearby;row['label']=LABELS.get(kind,kind)
            row['near_wrist_candidates']=hand_candidates(row,people) if kind in PORTABLE else []
            x1,y1,x2,y2=[int(v) for v in display];x1,x2=max(0,x1),min(width-1,x2);y1,y2=max(0,y1),min(height-1,y2)
            color=(145,210,165) if kind=='person' else (245,190,85)
            cv2.rectangle(frame,(x1,y1),(x2,y2),color,2,cv2.LINE_AA)
            label=f"{row['label']} {('#'+str(tid)) if tid is not None else '?'} {row['confidence']:.0%}"
            if kind=='person' and motion!='sem historico':label+=' | '+motion
            scale=max(.4,min(.65,width/1600));tw,th=cv2.getTextSize(label,cv2.FONT_HERSHEY_SIMPLEX,scale,1)[0]
            top=max(th+8,y1);cv2.rectangle(frame,(x1,top-th-8),(min(width-1,x1+tw+8),top),color,-1)
            cv2.putText(frame,label,(x1+4,top-5),cv2.FONT_HERSHEY_SIMPLEX,scale,(20,35,25),1,cv2.LINE_AA)
            points=row.get('keypoints',[])
            if len(points)==17:
                for a,b in LIMBS:
                    if points[a][2]>=.5 and points[b][2]>=.5:cv2.line(frame,tuple(int(v) for v in points[a][:2]),tuple(int(v) for v in points[b][:2]),(255,210,130),2,cv2.LINE_AA)
                for x,y,confidence in points:
                    if confidence>=.5:cv2.circle(frame,(int(x),int(y)),3,(255,210,130),-1,cv2.LINE_AA)
        return frame
