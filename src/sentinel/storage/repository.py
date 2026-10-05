import sqlite3,json
from contextlib import contextmanager
from pathlib import Path
class Repository:
    def __init__(self,path):
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        self.path=path
        with self.connect() as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, timestamp TEXT NOT NULL, camera TEXT, session_id TEXT, event_type TEXT, track_id INTEGER, object_type TEXT, zone TEXT, duration REAL, confidence REAL, status TEXT, metadata TEXT)")
            c.execute("CREATE INDEX IF NOT EXISTS events_time ON events(timestamp)")
            c.execute("CREATE TABLE IF NOT EXISTS incidents (id TEXT PRIMARY KEY, created_at TEXT, title TEXT, status TEXT, metadata TEXT)")
            c.execute("CREATE TABLE IF NOT EXISTS evidence (event_id TEXT PRIMARY KEY REFERENCES events(id), captured_at TEXT NOT NULL, jpeg BLOB NOT NULL)")
            c.execute("CREATE INDEX IF NOT EXISTS events_camera_time ON events(camera,timestamp)")
        self.init_visual()
    def init_visual(self):
        with self.connect() as c:
            c.execute("CREATE TABLE IF NOT EXISTS sessions (session_id TEXT PRIMARY KEY,camera TEXT,kind TEXT,name TEXT,started_at TEXT,ended_at TEXT,status TEXT)")
            if 'filename' not in {row[1] for row in c.execute('PRAGMA table_info(sessions)')}:c.execute('ALTER TABLE sessions ADD COLUMN filename TEXT')
            c.execute("CREATE TABLE IF NOT EXISTS visual_frames (id TEXT PRIMARY KEY,session_id TEXT,camera TEXT,timestamp TEXT,jpeg BLOB)")
            if 'offset_seconds' not in {row[1] for row in c.execute('PRAGMA table_info(visual_frames)')}:c.execute('ALTER TABLE visual_frames ADD COLUMN offset_seconds REAL')
            c.execute("CREATE INDEX IF NOT EXISTS visual_session_time ON visual_frames(session_id,timestamp)")
            c.execute("CREATE TABLE IF NOT EXISTS visual_reports (session_id TEXT PRIMARY KEY,status TEXT,result TEXT,error TEXT,updated_at TEXT)")
            c.execute("CREATE TABLE IF NOT EXISTS media_names (filename TEXT PRIMARY KEY,name TEXT)")
            c.execute("CREATE TABLE IF NOT EXISTS event_reviews (id INTEGER PRIMARY KEY AUTOINCREMENT,event_id TEXT NOT NULL,verdict TEXT NOT NULL,note TEXT NOT NULL,created_at TEXT NOT NULL)")
            c.execute("CREATE INDEX IF NOT EXISTS reviews_event ON event_reviews(event_id,id)")
            c.execute("CREATE TABLE IF NOT EXISTS evaluation_trials (id INTEGER PRIMARY KEY AUTOINCREMENT,task_id TEXT,mode TEXT,seconds REAL,outcome TEXT,created_at TEXT)")
    def trial_save(self,task_id,mode,seconds,outcome):
        from datetime import datetime,timezone
        with self.connect() as c:c.execute('INSERT INTO evaluation_trials(task_id,mode,seconds,outcome,created_at) VALUES (?,?,?,?,?)',(task_id,mode,seconds,outcome,datetime.now(timezone.utc).isoformat()))
    def trials(self):
        with self.connect() as c:return [dict(r) for r in c.execute('SELECT * FROM (SELECT * FROM evaluation_trials ORDER BY id DESC LIMIT 1000) ORDER BY id')]
    def review_save(self,event_id,verdict,note):
        from datetime import datetime,timezone
        with self.connect() as c:
            if not c.execute('SELECT 1 FROM events WHERE id=?',(event_id,)).fetchone():raise ValueError('Evento inexistente')
            c.execute('INSERT INTO event_reviews(event_id,verdict,note,created_at) VALUES (?,?,?,?)',(event_id,verdict,note,datetime.now(timezone.utc).isoformat()))
        return self.review(event_id)
    def review(self,event_id):
        with self.connect() as c:row=c.execute('SELECT event_id,verdict,note,created_at FROM event_reviews WHERE event_id=? ORDER BY id DESC LIMIT 1',(event_id,)).fetchone()
        return dict(row) if row else dict(event_id=event_id,verdict='not_reviewed',note='')
    def review_export(self,session_id):
        with self.connect() as c:
            rows=c.execute('SELECT e.id,e.session_id,e.camera,e.event_type,e.object_type,e.zone,e.timestamp,r.verdict,r.note,r.created_at FROM events e JOIN event_reviews r ON r.event_id=e.id WHERE e.session_id=? AND r.id=(SELECT MAX(x.id) FROM event_reviews x WHERE x.event_id=e.id) ORDER BY e.timestamp LIMIT 1000',(session_id,)).fetchall()
        return [dict(row) for row in rows]
    def register_session(self,session_id,camera,kind,name,started_at,filename=None):
        with self.connect() as c:c.execute('INSERT INTO sessions(session_id,camera,kind,name,started_at,ended_at,status,filename) VALUES (?,?,?,?,?,NULL,?,?)',(session_id,camera,kind,name,started_at,'running',filename))
    def session(self,session_id):
        with self.connect() as c:row=c.execute('SELECT * FROM sessions WHERE session_id=?',(session_id,)).fetchone()
        return dict(row) if row else None
    def end_session(self,session_id,ended_at,status):
        with self.connect() as c:c.execute('UPDATE sessions SET ended_at=?,status=? WHERE session_id=?',(ended_at,status,session_id))
    def visual_save(self,id,session_id,camera,timestamp,jpeg,keep=1200,offset_seconds=None):
        with self.connect() as c:
            c.execute('INSERT INTO visual_frames (id,session_id,camera,timestamp,jpeg,offset_seconds) VALUES (?,?,?,?,?,?)',(id,session_id,camera,timestamp,sqlite3.Binary(jpeg),offset_seconds))
            c.execute("DELETE FROM visual_frames WHERE session_id=? AND id NOT IN (SELECT id FROM visual_frames WHERE session_id=? ORDER BY timestamp DESC LIMIT ?) AND NOT EXISTS (SELECT 1 FROM visual_reports vr WHERE instr(COALESCE(vr.result,''),visual_frames.id)>0)",(session_id,session_id,keep))
    def visual_samples(self,session_id,since=None,until=None,limit=12,start_seconds=None,end_seconds=None):
        sql='SELECT id,session_id,camera,timestamp,offset_seconds FROM visual_frames WHERE session_id=?';args=[session_id]
        if since:sql+=' AND timestamp>=?';args.append(since)
        if until:sql+=' AND timestamp<?';args.append(until)
        if start_seconds is not None:sql+=' AND offset_seconds>=?';args.append(start_seconds)
        if end_seconds is not None:sql+=' AND offset_seconds<?';args.append(end_seconds)
        with self.connect() as c:rows=[dict(r) for r in c.execute(sql+' ORDER BY timestamp',args)]
        if len(rows)>limit:rows=[rows[round(i*(len(rows)-1)/(limit-1))] for i in range(limit)]
        return rows
    def visual_image(self,id):
        with self.connect() as c:
            row=c.execute('SELECT jpeg FROM visual_frames WHERE id=?',(id,)).fetchone()
            return bytes(row[0]) if row else None
    def visual_report(self,session_id):
        with self.connect() as c:row=c.execute('SELECT * FROM visual_reports WHERE session_id=?',(session_id,)).fetchone()
        if not row:return {'session_id':session_id,'status':'not_analyzed'}
        result=dict(row);result['result']=json.loads(result['result']) if result['result'] else None;return result
    def visual_report_save(self,session_id,status,result=None,error=None):
        from datetime import datetime,timezone
        with self.connect() as c:c.execute('INSERT OR REPLACE INTO visual_reports VALUES (?,?,?,?,?)',(session_id,status,json.dumps(result,ensure_ascii=False) if result else None,error,datetime.now(timezone.utc).isoformat()))
    def media_name(self,filename,name=None):
        with self.connect() as c:
            if name is not None:c.execute('INSERT OR REPLACE INTO media_names VALUES (?,?)',(filename,name))
            row=c.execute('SELECT name FROM media_names WHERE filename=?',(filename,)).fetchone();return row[0] if row else filename
    @contextmanager
    def connect(self):
        c=sqlite3.connect(self.path,timeout=10); c.row_factory=sqlite3.Row
        try:
            with c:yield c
        finally:c.close()
    def save(self,events,evidence=None):
        with self.connect() as c:
            for e in events:
                c.execute("INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",tuple(json.dumps(e[k],ensure_ascii=False) if k=="metadata" else e[k] for k in ["id","timestamp","camera","session_id","event_type","track_id","object_type","zone","duration","confidence","status","metadata"]))
                if evidence is not None and e['event_type'] in ('zone_enter','zone_exit','zone_dwell'):
                    c.execute("INSERT INTO evidence VALUES (?,?,?)",(e['id'],e['timestamp'],sqlite3.Binary(evidence)))
    def evidence(self,event_id):
        with self.connect() as c:
            row=c.execute("SELECT jpeg FROM evidence WHERE event_id=?",(event_id,)).fetchone()
            return bytes(row['jpeg']) if row else None
    def search(self,*,since,until,camera=None,session_id=None,event_type=None,object_type=None,zone=None,min_duration=0,limit=24,offset=0):
        clauses=['e.timestamp>=?','e.timestamp<?','e.duration>=?'];args=[since,until,min_duration]
        for field,value in [('camera',camera),('session_id',session_id),('event_type',event_type),('object_type',object_type),('zone',zone)]:
            if value is not None:clauses.append(f'e.{field}=?');args.append(value)
        where=' AND '.join(clauses)
        with self.connect() as c:
            total=c.execute('SELECT COUNT(*) FROM events e WHERE '+where,args).fetchone()[0]
            rows=c.execute('SELECT e.*,v.captured_at AS evidence_captured_at FROM events e LEFT JOIN evidence v ON v.event_id=e.id WHERE '+where+' ORDER BY e.timestamp DESC,e.rowid DESC LIMIT ? OFFSET ?',[*args,limit,offset]).fetchall()
        items=[]
        for row in rows:
            values=dict(row);captured=values.pop('evidence_captured_at');item=self.decode(values)
            item.update(evidence_available=captured is not None,evidence_captured_at=captured)
            items.append(item)
        return dict(items=items,total=total,limit=limit,offset=offset,has_more=offset+len(items)<total)
    def catalog(self):
        with self.connect() as c:
            return {field:[r[0] for r in c.execute(f'SELECT DISTINCT {field} FROM events WHERE {field} IS NOT NULL ORDER BY {field}')] for field in ['camera','zone']}
    def sessions(self):
        with self.connect() as c:
            return [dict(row) for row in c.execute("SELECT x.session_id,x.camera,COALESCE(s.started_at,MIN(e.timestamp)) started_at,COALESCE(s.ended_at,MAX(e.timestamp)) ended_at,COUNT(e.id) count,s.kind,s.name,s.filename,s.status,(SELECT COUNT(*) FROM visual_frames v WHERE v.session_id=x.session_id) visual_count FROM (SELECT session_id,camera FROM sessions UNION SELECT session_id,camera FROM events) x LEFT JOIN sessions s ON s.session_id=x.session_id LEFT JOIN events e ON e.session_id=x.session_id AND e.camera=x.camera GROUP BY x.session_id,x.camera ORDER BY started_at DESC")]

    def search_stats(self,*,since,until,camera=None,session_id=None,event_type=None,object_type=None,zone=None,min_duration=0):
        clauses=['timestamp>=?','timestamp<?','duration>=?'];args=[since,until,min_duration]
        for field,value in [('camera',camera),('session_id',session_id),('event_type',event_type),('object_type',object_type),('zone',zone)]:
            if value is not None:clauses.append(f'{field}=?');args.append(value)
        with self.connect() as c:
            return [dict(row) for row in c.execute('SELECT event_type,object_type,COUNT(*) count FROM events WHERE '+' AND '.join(clauses)+' GROUP BY event_type,object_type',args)]
    @staticmethod
    def decode(row):
        e=dict(row); e["metadata"]=json.loads(e["metadata"]); return e
    def query(self,since=None,until=None,camera=None,event_type=None,limit=100,offset=0):
        sql="SELECT * FROM events WHERE 1=1"; args=[]
        for field,value,op in [("timestamp",since,">="),("timestamp",until,"<="),("camera",camera,"="),("event_type",event_type,"=")]:
            if value is not None: sql+=f" AND {field} {op} ?"; args.append(value)
        sql+=" ORDER BY timestamp DESC, rowid DESC LIMIT ? OFFSET ?"; args.extend([limit,offset])
        with self.connect() as c:return [self.decode(row) for row in c.execute(sql,args)]
    def get(self,id):
        with self.connect() as c:
            row=c.execute("SELECT * FROM events WHERE id=?",(id,)).fetchone()
            return self.decode(row) if row else None
    def status(self,id,status):
        with self.connect() as c:return c.execute("UPDATE events SET status=? WHERE id=?",(status,id)).rowcount
    def stats(self,since=None,until=None,camera=None):
        sql="SELECT event_type,object_type,COUNT(*) count FROM events WHERE 1=1"; args=[]
        if since:sql+=" AND timestamp>=?"; args.append(since)
        if until:sql+=" AND timestamp<=?"; args.append(until)
        if camera is not None:sql+=" AND camera=?"; args.append(camera)
        with self.connect() as c:return [dict(row) for row in c.execute(sql+" GROUP BY event_type,object_type",args)]
