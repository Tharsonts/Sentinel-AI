from pathlib import Path
from sentinel.events.engine import Detection
from sentinel.vision.overlay import SCOPES,QUALITIES,TrackOverlay,box_iou
import time,tempfile
from sentinel.config import ROOT
class YoloTracker:
    def __init__(self,settings):
        if not Path(settings.model_name).is_file():raise ValueError("Pesos YOLO ausentes. Configure MODEL_NAME com arquivo local; download automÃ¡tico desabilitado.")
        from ultralytics import YOLO
        self.model=YOLO(settings.model_name); self.settings=settings
        specialist_path=getattr(settings,'person_specialist_model_name','')
        if specialist_path and not Path(specialist_path).is_file():
            raise ValueError('Pesos do reforÃ§o de pessoas ausentes; configure um arquivo local vÃ¡lido.')
        self.specialist=YOLO(specialist_path) if specialist_path else None
        if self.specialist is not None and self.specialist.names!={0:'person'}:
            raise ValueError('O reforÃ§o deve ser um detector treinado exclusivamente para person.')
        self.fusion_tracker=None
        self.options={'scope':'objects','quality':'balanced','confidence':settings.confidence}
        self.overlay=TrackOverlay();self.observations=[]
        (ROOT/'work').mkdir(exist_ok=True)
        with tempfile.NamedTemporaryFile(mode='w',suffix='.yaml',prefix='sentinel-tracker-',dir=ROOT/'work',delete=False,encoding='utf-8') as f:self.tracker_config=Path(f.name)
        self.configured_confidence=None
        pose_path=Path(getattr(settings,'pose_model_name',''))
        self.pose=YOLO(str(pose_path)) if pose_path.is_file() else None
    def process(self,frame):
        threshold=self.options['confidence']
        if self.configured_confidence!=threshold:
            self.tracker_config.write_text(f'tracker_type: bytetrack\ntrack_high_thresh: {threshold}\ntrack_low_thresh: 0.1\nnew_track_thresh: {threshold}\ntrack_buffer: 30\nmatch_thresh: 0.8\nfuse_score: false\n',encoding='utf-8')
            predictor=getattr(self.model,'predictor',None)
            for tracker in getattr(predictor,'trackers',[]):
                tracker.args.track_high_thresh=threshold;tracker.args.new_track_thresh=threshold
            self.configured_confidence=threshold
        if getattr(self,'specialist',None) is not None:
            result=self._process_fused(frame,threshold)
        else:
            result=self.model.track(frame,persist=True,tracker=str(self.tracker_config),device=self.settings.device,
                imgsz=QUALITIES[self.options['quality']],conf=.1,classes=SCOPES[self.options['scope']],verbose=False)[0]
        boxes=result.boxes; detections=[];rows=[]
        if boxes is not None:
            ids=boxes.id.cpu().tolist() if boxes.id is not None else [None]*len(boxes.xyxy)
            for box,tid,cls,conf in zip(boxes.xyxy.cpu().tolist(),ids,boxes.cls.cpu().tolist(),boxes.conf.cpu().tolist()):
                tid=int(tid) if tid is not None else None;kind=result.names[int(cls)]
                if tid is None and conf<threshold:continue
                rows.append(dict(track_id=tid,object_type=kind,confidence=round(float(conf),4),box=box,tracking_recovery=conf<threshold))
                if tid is not None:detections.append(Detection(tid,kind,float(conf),tuple(box)))
        if self.pose is not None and any(r['object_type']=='person' for r in rows):
            pose=self.pose.predict(frame,device=self.settings.device,imgsz=min(960,QUALITIES[self.options['quality']]),conf=.4,verbose=False)[0]
            if pose.keypoints is not None and pose.keypoints.conf is not None:
                candidates=[]
                for i,pose_box in enumerate(pose.boxes.xyxy.cpu().tolist()):
                    for j,row in enumerate(rows):
                        if row['object_type']=='person' and box_iou(row['box'],pose_box)>.3:candidates.append((box_iou(row['box'],pose_box),i,j))
                used_pose=set();used_rows=set()
                xy=pose.keypoints.xy.cpu().tolist();conf=pose.keypoints.conf.cpu().tolist()
                for _,i,j in sorted(candidates,reverse=True):
                    if i in used_pose or j in used_rows:continue
                    used_pose.add(i);used_rows.add(j)
                    rows[j]['keypoints']=[[float(x),float(y),round(float(c),3)] for (x,y),c in zip(xy[i],conf[i])]
        self.observations=rows
        return detections,self.overlay.draw(frame.copy(),rows,getattr(self,'source_timestamp',time.monotonic()))
    def _process_fused(self,frame,threshold):
        import numpy as np
        import torch
        from types import SimpleNamespace
        from ultralytics.engine.results import Boxes
        from ultralytics.trackers.byte_tracker import BYTETracker
        from sentinel.vision.fusion import supplement_people
        kwargs=dict(device=self.settings.device,imgsz=QUALITIES[self.options['quality']],conf=.1,verbose=False)
        result=self.model.predict(frame,classes=SCOPES[self.options['scope']],**kwargs)[0]
        if SCOPES[self.options['scope']] is None or 0 in SCOPES[self.options['scope']]:
            trained=self.specialist.predict(frame,classes=[0],**kwargs)[0]
            def unpack(boxes):
                if boxes is None:return []
                cpu=boxes.cpu().numpy()
                return [(box,score) for box,score,cls in zip(cpu.xyxy.tolist(),cpu.conf.tolist(),cpu.cls.tolist()) if int(cls)==0]
            combined=supplement_people(unpack(result.boxes),unpack(trained.boxes),
                max(threshold,self.settings.person_specialist_threshold),base_threshold=threshold)
            other=result.boxes.cpu().numpy().data.tolist() if result.boxes is not None else []
            values=np.asarray([[*box,score,0] for box,score in combined]+[row for row in other if int(row[5])!=0],dtype=np.float32).reshape(-1,6)
            result.boxes=Boxes(values,frame.shape[:2])
        if self.fusion_tracker is None:
            self.fusion_tracker=BYTETracker(SimpleNamespace(track_high_thresh=threshold,track_low_thresh=.1,
                new_track_thresh=threshold,track_buffer=30,match_thresh=.8,fuse_score=False),frame_rate=30)
        self.fusion_tracker.args.track_high_thresh=threshold
        self.fusion_tracker.args.new_track_thresh=threshold
        tracked=self.fusion_tracker.update(result.boxes.cpu().numpy(),img=frame)
        result.boxes=Boxes(torch.as_tensor(np.asarray(tracked,dtype=np.float32).reshape(-1,8)[:,:7]),frame.shape[:2])
        return result
    def close(self):
        path=getattr(self,'tracker_config',None)
        if path:path.unlink(missing_ok=True)
    def __del__(self):
        self.close()
