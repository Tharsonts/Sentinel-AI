import pytest
from sentinel.presence_predictions import export_session
from sentinel.storage.repository import Repository
from sentinel.events.engine import EventEngine,Zone,Detection

def test_video_time_uses_frame_offset_and_is_session_scoped(tmp_path):
 r=Repository(str(tmp_path/'db'))
 with r.connect() as c:
  c.execute("INSERT INTO sessions(session_id,kind) VALUES ('S','file')")
  c.execute("INSERT INTO visual_frames(id,session_id,timestamp,offset_seconds) VALUES ('F','S','1970-01-01T00:01:45+00:00',5)")
 e=EventEngine([Zone(id='R',name='R',polygon=[(0,0),(1,0),(1,1),(0,1)])],'C','S')
 r.save(e.update([Detection(1,'person',.9,(10,10,20,20))],100,100,110))
 r.save(e.close(111,'source_ended'))
 data=export_session(r,'S','V');assert len(data['V'])==1 and data['V'][0]['offset_seconds']==10
 with pytest.raises(ValueError):export_session(r,'missing','V')

def test_no_video_clock_must_not_guess(tmp_path):
 r=Repository(str(tmp_path/'db'))
 with r.connect() as c:c.execute("INSERT INTO sessions(session_id,kind) VALUES ('S','file')")
 with pytest.raises(ValueError):export_session(r,'S','V')
