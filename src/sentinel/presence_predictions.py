"""Export recorded events in file-video time, without guessing annotations."""
from datetime import datetime

def export_session(repository,session_id,recording_id):
    with repository.connect() as c:
        session=c.execute('SELECT kind FROM sessions WHERE session_id=?',(session_id,)).fetchone()
        if session is None or session['kind']!='file':raise ValueError('Selecione uma sessão de arquivo de vídeo.')
        frame=c.execute('SELECT timestamp,offset_seconds FROM visual_frames WHERE session_id=? AND offset_seconds IS NOT NULL ORDER BY offset_seconds LIMIT 1',(session_id,)).fetchone()
        if frame is None:raise ValueError('Sessão sem referência temporal; reprocesse o vídeo.')
        base=datetime.fromisoformat(frame['timestamp']).timestamp()-frame['offset_seconds']
        rows=c.execute("SELECT id,event_type,zone,timestamp FROM events WHERE session_id=? AND event_type IN ('zone_enter','zone_dwell','zone_exit') ORDER BY timestamp",(session_id,)).fetchall()
    events=[]
    for row in rows:
        offset=datetime.fromisoformat(row['timestamp']).timestamp()-base
        if offset<-.001:raise ValueError('Evento anterior à origem do vídeo.')
        events.append(dict(event_id=row['id'],event_type=row['event_type'],zone=row['zone'],offset_seconds=round(max(0,offset),6)))
    return {recording_id:events}
