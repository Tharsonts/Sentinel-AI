from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
ROOT = Path(__file__).resolve().parents[2]
class Settings(BaseSettings):
    server_host: str = "127.0.0.1"
    server_port: int = 8000
    api_key: str
    model_name: str = str(ROOT / "models/yolo11n.pt")
    pose_model_name: str = str(ROOT / "models/yolo11n-pose.pt")
    person_specialist_model_name: str = ""
    person_specialist_threshold: float = Field(default=0.75, ge=0.1, le=1)
    device: str = "0"
    image_size: int = 640
    max_frame_dimension: int = Field(default=1280, ge=320, le=4096)
    visual_sample_seconds: float = Field(default=1.0, ge=0.5, le=60)
    visual_frames_per_session: int = Field(default=1200, ge=6, le=10000)
    confidence: float = 0.3
    llm_base_url: str = "http://127.0.0.1:11434"
    llm_model: str = "qwen3.5:9b"
    llm_provider: str = "ollama"
    llm_api_key: str = ""
    database_path: str = str(ROOT / "data/sentinel.db")
    media_dir: str = str(ROOT / "data/media")
    camera_profile_path: str = str(ROOT / "config/camera.local.json")
    detection_profile_path: str = str(ROOT / "config/detection.local.json")
    zones_path: str = str(ROOT / "config/zones.json")
    lost_timeout: float = 2.0
    zone_confirmation_seconds: float = Field(default=0.4,ge=0,le=5)
    max_upload_mb: int = 100
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
