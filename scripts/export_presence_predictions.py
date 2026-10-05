import argparse,json
from pathlib import Path
from sentinel.presence_predictions import export_session
from sentinel.storage.repository import Repository
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--database',required=True);p.add_argument('--session',required=True);p.add_argument('--recording-id',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 if not Path(a.database).is_file():raise ValueError('Banco inexistente.')
 data=export_session(Repository(a.database),a.session,a.recording_id)
 Path(a.output).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');print('Previsões exportadas. Isto não é referência anotada.')
