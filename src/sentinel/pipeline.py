import threading,time,json

from pathlib import Path

from uuid import uuid4

from datetime import datetime,timezone

import cv2,numpy as np

from sentinel.events.engine import EventEngine,Zone

from sentinel.video.sources import FileVideoSource,WebcamVideoSource,RTSPVideoSource

from sentinel.vision.detector import YoloTracker

class Pipeline:

    def __init__(self,settings,repo,backend_factory=YoloTracker):

        self.backend_factory=backend_factory

        self.settings,self.repo=settings,repo; self.lock=threading.RLock(); self.stop_flag=threading.Event()

        self.on_session_end=None; self.last_visual_at=None; self.last_visual_review=None

        self.thread=None; self.jpg=None; self.engine=None; self.tracker=None

        self.state={"status":"idle","frames":0,"fps":0,"inference_ms":0,"error":None}
        self.detection_options={'scope':'objects','quality':'balanced','confidence':settings.confidence if hasattr(settings,'confidence') else .3}

    def zones(self):return [Zone.model_validate(z) for z in json.loads(Path(self.settings.zones_path).read_text(encoding="utf-8"))]

    def start(self,kind,source,camera):

        with self.lock:

            if self.state["status"] in ("running","starting","stopping"):raise ValueError("Uma câmera já está ativa")

            self.stop_flag.clear(); self.jpg=None

            self.state=dict(status="starting",frames=0,fps=0,inference_ms=0,error=None,session_id=str(uuid4()),camera=camera,kind=kind)

            self.last_visual_at=None; self.last_visual_review=None

            name=self.repo.media_name(Path(source).name) if kind=='file' else {'push':'Webcam do notebook','rtsp':'Câmera IP','webcam':'Webcam do PC'}.get(kind,kind)

            self.repo.register_session(self.state['session_id'],camera,kind,name,datetime.now(timezone.utc).isoformat(),Path(source).name if kind=='file' else None)

            self.thread=threading.Thread(target=self.run,args=(kind,source),daemon=True); self.thread.start()

    def run(self,kind,source):

        video=None; end_reason="source_ended"

        try:

            self.tracker=self.backend_factory(self.settings)
            if hasattr(self.tracker,'options'):self.tracker.options=dict(self.detection_options)

            self.engine=EventEngine(self.zones(),self.state["camera"],self.state["session_id"],self.settings.lost_timeout,getattr(self.settings,'zone_confirmation_seconds',.4))

            if kind=="push":

                with self.lock:self.state["status"]="running"

                while not self.stop_flag.wait(.5):

                    with self.lock:

                        if self.state.get("last_frame_at") and time.time()-self.state["last_frame_at"]>self.settings.lost_timeout:

                            self.repo.save(self.engine.update([],1,1,time.time()))

                end_reason="operator_stopped"; return

            video={"file":FileVideoSource,"webcam":WebcamVideoSource,"rtsp":RTSPVideoSource}[kind](source)
            if kind=='file':
                duration=video.cap.get(cv2.CAP_PROP_FRAME_COUNT)/max(video.fps,1)
                with self.lock:self.state.update(video_duration_seconds=duration,visual_interval_seconds=min(self.settings.visual_sample_seconds,max(.25,duration/12)))

            base=time.time(); count=0; retries=0
            with self.lock:self.state['source_started_at']=base

            with self.lock:self.state["status"]="running"

            while not self.stop_flag.is_set():

                ok,frame=video.read()

                if not ok:
                    if kind!='rtsp':break
                    with self.lock:self.state['reconnecting']=True
                    video.close();retries+=1
                    if retries>3:raise ValueError('Conexão da câmera interrompida. Verifique a rede e inicie novamente.')
                    if self.stop_flag.wait(min(2**retries,8)):break
                    try:video=RTSPVideoSource(source)
                    except ValueError:continue
                    continue
                retries=0
                with self.lock:self.state['reconnecting']=False

                timestamp=base+count/video.fps if kind=="file" else time.time()

                self.process(frame,timestamp)

                count+=1

                if kind=="file":self.stop_flag.wait(max(0,base+count/video.fps-time.time()))

            if self.stop_flag.is_set():end_reason="operator_stopped"

        except Exception as e:

            end_reason="processing_error"

            with self.lock:self.state["status"]="error"; self.state["error"]=str(e)

        finally:

            if video:video.close()

            with self.lock:

                if self.engine:self.repo.save(self.engine.close(time.time(),end_reason))

                finished_session=self.state["session_id"]
                self.repo.end_session(finished_session,datetime.now(timezone.utc).isoformat(),end_reason)

                if hasattr(self.tracker,'close'):self.tracker.close()
                self.tracker=None; self.engine=None

                if self.state["status"]!="error":self.state["status"]="stopped"

            if self.on_session_end and end_reason!="processing_error":self.on_session_end(finished_session)

    def process(self,frame,timestamp=None,expected_camera=None,expected_session=None,require_push=False):

        with self.lock:

            if require_push and (self.state.get('kind')!='push' or self.state['status']!='running'):

                raise ValueError('Inicie uma câmera do tipo push')

            if expected_camera is not None and self.state.get('camera')!=expected_camera:

                raise ValueError('Outra câmera está ativa; o frame não foi processado')

            if expected_session is not None and self.state.get('session_id')!=expected_session:

                raise ValueError('A sessão mudou; reconecte antes de enviar outro frame')

            if self.tracker is None or self.engine is None:raise ValueError("Processamento indisponível")

            # Bound annotation/JPEG/storage work too, not only the YOLO input.

            # Normalized zones remain valid after proportional scaling.

            begin=time.perf_counter()

            height,width=frame.shape[:2]

            maximum=self.settings.max_frame_dimension

            if maximum<320 or maximum>4096:raise ValueError('MAX_FRAME_DIMENSION deve estar entre 320 e 4096')

            if max(height,width)>maximum:

                scale=maximum/max(height,width)

                frame=cv2.resize(frame,(max(1,round(width*scale)),max(1,round(height*scale))),interpolation=cv2.INTER_AREA)

            capture_time=timestamp if timestamp is not None else time.time()

            interval=self.state.get('visual_interval_seconds',getattr(self.settings,'visual_sample_seconds',2))
            if self.last_visual_at is None or capture_time-self.last_visual_at>=interval-1e-6:

                raw=frame.copy();rh,rw=raw.shape[:2];scale=min(1,1024/max(rh,rw))

                if scale<1:raw=cv2.resize(raw,(max(1,round(rw*scale)),max(1,round(rh*scale))))

                encoded_ok,raw_jpeg=cv2.imencode('.jpg',raw,[cv2.IMWRITE_JPEG_QUALITY,85])

                if encoded_ok:

                    offset=max(0,capture_time-self.state['source_started_at']) if self.state.get('kind')=='file' and 'source_started_at' in self.state else None
                    self.repo.visual_save(str(uuid4()),self.state.get('session_id',self.engine.session),self.state.get('camera',self.engine.camera),datetime.fromtimestamp(capture_time,timezone.utc).isoformat(),raw_jpeg.tobytes(),getattr(self.settings,'visual_frames_per_session',1200),offset_seconds=offset)

                    self.last_visual_at=capture_time

            if self.last_visual_review is None:self.last_visual_review=capture_time
            if self.state.get('kind') in ('push','rtsp','webcam') and capture_time-self.last_visual_review>=60 and self.on_session_end:
                self.last_visual_review=capture_time;self.on_session_end(self.state.get('session_id',self.engine.session))
            self.tracker.source_timestamp=capture_time
            detections,annotated=self.tracker.process(frame)
            self.engine.min_entry_confidence=self.detection_options['confidence']
            self.state['observations']=getattr(self.tracker,'observations',[])[:100]
            self.state['detection_options']=dict(self.detection_options)

            h,w=frame.shape[:2]; events=self.engine.update(detections,w,h,timestamp or time.time())

            for z in self.engine.zones:

                pts=np.array([(x*w,y*h) for x,y in z.polygon],np.int32)

                cv2.polylines(annotated,[pts],True,(0,200,255),2)

                cv2.putText(annotated,z.name,tuple(pts[0]),cv2.FONT_HERSHEY_SIMPLEX,.6,(0,200,255),2)

            ok,encoded=cv2.imencode(".jpg",annotated,[cv2.IMWRITE_JPEG_QUALITY,80])

            if ok:self.jpg=encoded.tobytes()

            # Only a current processed frame can be evidence of these events.

            # Timeout/end-of-source events intentionally have no invented image.

            self.repo.save(events,encoded.tobytes() if ok else None)

            ms=(time.perf_counter()-begin)*1000

            self.state.update(frames=self.state["frames"]+1,inference_ms=round(ms,2),fps=round(1000/max(ms,.01),2),objects=len(detections),last_frame_at=time.time())

            return {"detections":[d.__dict__ for d in detections],"events":events}

    def stop(self):

        self.stop_flag.set()

        with self.lock:

            if self.state["status"] in ("running","starting"):self.state["status"]="stopping"

        if self.thread:self.thread.join(timeout=10)

        return self.snapshot()

    def snapshot(self):

        with self.lock:

            state=dict(self.state)

            age=max(0,time.time()-state['last_frame_at']) if state.get('last_frame_at') else None

            state.update(last_frame_age_seconds=round(age,1) if age is not None else None,

                         receiving=state['status']=='running' and not state.get('reconnecting',False) and age is not None and age<5)

            return state
