import os
from pathlib import Path
from sentinel.config import ROOT,Settings
for name,path in {"YOLO_CONFIG_DIR":ROOT/"cache/ultralytics","TORCH_HOME":ROOT/"cache/torch","TEMP":ROOT/"work","TMP":ROOT/"work"}.items():
    Path(path).mkdir(parents=True,exist_ok=True);os.environ[name]=str(path)
os.environ["YOLO_AUTOINSTALL"]="false"
import uvicorn
if __name__=="__main__":
    s=Settings();uvicorn.run("sentinel.api:app",host=s.server_host,port=s.server_port,workers=1)
