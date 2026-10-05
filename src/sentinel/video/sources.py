from pathlib import Path
import cv2
class VideoSource:
    def __init__(self, source):
        self.cap=cv2.VideoCapture(source)
        if not self.cap.isOpened():
            self.cap.release(); raise ValueError("Não foi possível abrir a fonte de vídeo")
        self.fps=self.cap.get(cv2.CAP_PROP_FPS) or 25
    def read(self):return self.cap.read()
    def close(self):self.cap.release()
class FileVideoSource(VideoSource):
    def __init__(self,source):
        if not Path(source).is_file():raise ValueError("Arquivo de vídeo inexistente")
        super().__init__(str(source))
class WebcamVideoSource(VideoSource):
    def __init__(self,index):super().__init__(int(index))
class RTSPVideoSource(VideoSource):
    def __init__(self,source):
        self.cap=cv2.VideoCapture(source,cv2.CAP_FFMPEG,[cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,5000,cv2.CAP_PROP_READ_TIMEOUT_MSEC,5000])
        if not self.cap.isOpened():
            self.cap.release(); raise ValueError("Não foi possível abrir a fonte RTSP")
        self.fps=self.cap.get(cv2.CAP_PROP_FPS) or 25
