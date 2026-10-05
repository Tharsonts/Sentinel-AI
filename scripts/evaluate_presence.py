import argparse,json
from pathlib import Path
from sentinel.presence_evaluation import evaluate_events
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--reference',required=True);p.add_argument('--predictions',required=True);p.add_argument('--split',choices=['validation','test'],default='test');p.add_argument('--output',required=True);a=p.parse_args()
 result=evaluate_events(json.loads(Path(a.reference).read_text(encoding='utf-8-sig')),json.loads(Path(a.predictions).read_text(encoding='utf-8-sig')),a.split)
 Path(a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False))
