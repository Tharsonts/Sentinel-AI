from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4
import cv2
import numpy as np
from pydantic import BaseModel, Field, model_validator

class Zone(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=100)
    polygon: list[tuple[float, float]] = Field(min_length=3, max_length=30)
    dwell_seconds: float = Field(default=10, ge=0.1, le=86400)
    classes: list[str] = Field(default_factory=lambda: ["person", "car", "motorcycle", "bicycle", "bus", "truck"])
    @model_validator(mode="after")
    def valid_polygon(self):
        if any(not (0 <= x <= 1 and 0 <= y <= 1) for x,y in self.polygon):
            raise ValueError("Coordenadas de zona devem estar entre 0 e 1")
        if abs(cv2.contourArea(np.array(self.polygon, dtype=np.float32))) < 0.00001:
            raise ValueError("Polígono sem área")
        return self

@dataclass
class Detection:
    track_id: int
    object_type: str
    confidence: float
    box: tuple[float,float,float,float]

class EventEngine:
    def __init__(self, zones, camera, session, lost_timeout=2,confirmation_seconds=0):
        self.zones, self.camera, self.session = zones, camera, session
        self.lost_timeout = lost_timeout
        self.active = {}
        self.confirmation_seconds=confirmation_seconds
        self.pending_in={};self.pending_out={}
        self.min_entry_confidence=0
        self.last_update=None;self.supported={};self.last_strong={}
    def event(self, kind, d, z, t, duration=0, metadata=None):
        return dict(id=str(uuid4()), event_type=kind, track_id=d.track_id,
            object_type=d.object_type, confidence=round(d.confidence,4), zone=z.id,
            camera=self.camera, session_id=self.session,
            timestamp=datetime.fromtimestamp(t,timezone.utc).isoformat(),
            duration=round(max(0,duration),3), metadata=metadata or {}, status="new")
    def update(self, detections, width, height, timestamp):
        out=[]; seen=set();inside_keys=set();strong_keys=set()
        if self.last_update is not None and timestamp<self.last_update:
            raise ValueError('Timestamps devem ser monotônicos')
        if self.last_update is not None and timestamp-self.last_update>self.lost_timeout:
            out.extend(self.event('track_lost',state[3],state[4],timestamp,state[1]-state[0],{'reason':'observation_gap','exit_confirmed':False}) for state in self.active.values())
            self.active.clear();self.pending_in.clear();self.pending_out.clear();self.supported.clear();self.last_strong.clear()
        self.last_update=timestamp
        # Expire before processing a returning ID; heartbeats cannot bridge absence.
        for key,state in list(self.active.items()):
            if timestamp-state[1]>self.lost_timeout:
                self.active.pop(key);self.pending_out.pop(key,None)
                self.last_strong.pop(key,None);self.supported.pop(key,None)
                out.append(self.event('track_lost',state[3],state[4],timestamp,state[1]-state[0],{'reason':'detection_missing','exit_confirmed':False}))
        for d in detections:
            for z in self.zones:
                key=(d.track_id,z.id)
                # Ground contact: centro inferior do bounding box.
                point=((d.box[0]+d.box[2])/2/width, d.box[3]/height)
                inside=d.object_type in z.classes and cv2.pointPolygonTest(np.array(z.polygon,np.float32),point,False)>=0
                if inside:
                    if key not in self.active and d.confidence<self.min_entry_confidence:continue
                    inside_keys.add(key);self.pending_out.pop(key,None)
                    seen.add(key)
                    if key not in self.active:
                        first=self.pending_in.setdefault(key,timestamp)
                        if timestamp-first+1e-6<self.confirmation_seconds:continue
                        self.pending_in.pop(key,None)
                        self.active[key]=[first,timestamp,False,d,z]
                        self.supported[key]=timestamp-first;self.last_strong[key]=timestamp
                        metadata={'confirmation_seconds':self.confirmation_seconds,'first_seen_at':datetime.fromtimestamp(first,timezone.utc).isoformat()} if self.confirmation_seconds else None
                        out.append(self.event("zone_enter",d,z,timestamp,metadata=metadata))
                    state=self.active[key]; state[1]=timestamp; state[3]=d
                    if d.confidence>=self.min_entry_confidence:
                        strong_keys.add(key)
                        previous=self.last_strong.get(key)
                        if previous is not None:self.supported[key]=self.supported.get(key,0)+max(0,timestamp-previous)
                        self.last_strong[key]=timestamp
                    if not state[2] and self.supported.get(key,0)+1e-6>=z.dwell_seconds and d.confidence>=self.min_entry_confidence:
                        state[2]=True
                        out.append(self.event("zone_dwell",d,z,timestamp,timestamp-state[0],{"observed_seconds":round(self.supported[key],3),"basis":"strong_inside_observations"}))
                elif key in self.active:
                    if d.confidence<self.min_entry_confidence:
                        self.pending_out.pop(key,None);continue
                    first=self.pending_out.setdefault(key,timestamp)
                    if timestamp-first+1e-6<self.confirmation_seconds:continue
                    self.pending_out.pop(key,None)
                    state=self.active.pop(key)
                    out.append(self.event("zone_exit",d,z,timestamp,timestamp-state[0]))
        self.last_strong={key:t for key,t in self.last_strong.items() if key in strong_keys and key in self.active}
        self.supported={key:t for key,t in self.supported.items() if key in self.active}
        self.pending_in={key:t for key,t in self.pending_in.items() if key in inside_keys}
        # A missing detection cannot confirm an outside observation sequence.
        observed={(d.track_id,z.id) for d in detections for z in self.zones}
        self.pending_out={key:t for key,t in self.pending_out.items() if key in observed and key in self.active}
        for key,state in list(self.active.items()):
            if key not in seen and timestamp-state[1]>self.lost_timeout:
                self.active.pop(key)
                self.pending_out.pop(key,None)
                out.append(self.event("track_lost",state[3],state[4],timestamp,state[1]-state[0],{"reason":"detection_missing", "exit_confirmed":False}))
        return out
    def close(self, timestamp, reason):
        out=[self.event("presence_ended",s[3],s[4],timestamp,s[1]-s[0],{"reason":reason,"exit_confirmed":False}) for s in self.active.values()]
        self.active.clear();self.pending_in.clear();self.pending_out.clear();self.supported.clear();self.last_strong.clear();return out
