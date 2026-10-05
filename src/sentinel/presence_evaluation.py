"""Event evaluation against fully reviewed references, never model-generated labels."""
import math
from statistics import median

KINDS={'zone_enter','zone_dwell','zone_exit'}

def validate_reference(data):
    rows=data.get('recordings',[])
    if not rows:raise ValueError('Sem gravações anotadas: avaliação indisponível.')
    ids=set();groups={}
    for row in rows:
        if row['id'] in ids:raise ValueError('Gravação duplicada.')
        ids.add(row['id']);group=row['source_group'];split=row['split']
        if split not in {'train','validation','test'}:raise ValueError('Split inválido.')
        if group in groups and groups[group]!=split:raise ValueError('Mesma origem em treino e teste.')
        groups[group]=split
        if not row.get('reviewed_full_video') or not row.get('reviewer') or row.get('reference_origin')!='manual':raise ValueError('Referência exige revisão manual completa.')
        duration=row['duration_seconds']
        if not math.isfinite(duration) or duration<=0:raise ValueError('Duração inválida.')
        for event in row['expected_events']:
            if event['event_type'] not in KINDS:raise ValueError('Tipo de referência inválido.')
            a,b=event['window_seconds'];anchor=event['reference_seconds']
            if not all(math.isfinite(t) for t in [a,b,anchor]) or not 0<=anchor<=a<=b<=duration:raise ValueError('Janela de referência inválida.')
        for a,b in row.get('unverifiable_intervals',[]):
            if not all(math.isfinite(t) for t in [a,b]) or not 0<=a<b<=duration:raise ValueError('Intervalo ambíguo inválido.')
    return rows

def evaluate_events(reference,predictions,split='test'):
    rows=[r for r in validate_reference(reference) if r['split']==split]
    if not rows:raise ValueError('Sem gravações para o split selecionado.')
    totals={'tp':0,'fp':0,'fn':0};seconds=0;delays=[];ignored=0;details=[]
    for row in rows:
        rid=row['id']
        if rid not in predictions:raise ValueError('Faltam previsões para '+rid+'. Use lista vazia para zero eventos.')
        ambiguous=row.get('unverifiable_intervals',[])
        intervals=[]
        for a,b in sorted(ambiguous):
            if intervals and a<=intervals[-1][1]:intervals[-1][1]=max(b,intervals[-1][1])
            else:intervals.append([a,b])
        seconds+=row['duration_seconds']-sum(b-a for a,b in intervals)
        truth=[]
        for event in row['expected_events']:
            a,b=event['window_seconds']
            if any(a<=d and b>=c for c,d in intervals):raise ValueError('Referência sobreposta a intervalo não verificável.')
            truth.append(event)
        actual=[]
        for event in predictions[rid]:
            t=event['offset_seconds']
            if not math.isfinite(t) or not 0<=t<=row['duration_seconds']:raise ValueError('Tempo previsto fora da gravação.')
            if event['event_type'] not in KINDS:continue
            if any(a<=t<=b for a,b in intervals):ignored+=1;continue
            actual.append(event)
        actual.sort(key=lambda e:e['offset_seconds'])
        edges=[[j for j,t in enumerate(truth) if p['event_type']==t['event_type'] and p['zone']==t['zone'] and t['window_seconds'][0]<=p['offset_seconds']<=t['window_seconds'][1]] for p in actual]
        owners={}
        def augment(i,visited):
            for j in edges[i]:
                if j in visited:continue
                visited.add(j)
                if j not in owners or augment(owners[j],visited):owners[j]=i;return True
            return False
        for i in range(len(actual)):augment(i,set())
        tp=len(owners);counts=dict(tp=tp,fp=len(actual)-tp,fn=len(truth)-tp)
        for key in totals:totals[key]+=counts[key]
        delays.extend(actual[i]['offset_seconds']-truth[j]['reference_seconds'] for j,i in owners.items())
        details.append(dict(recording=rid,**counts))
    precision=totals['tp']/(totals['tp']+totals['fp']) if totals['tp']+totals['fp'] else None
    recall=totals['tp']/(totals['tp']+totals['fn']) if totals['tp']+totals['fn'] else None
    return dict(**totals,precision=precision,recall=recall,reviewed_hours=seconds/3600,false_alerts_per_hour=totals['fp']/(seconds/3600) if seconds else None,median_alert_delay_seconds=median(delays) if delays else None,ignored_predictions=ignored,recordings=details,operational_approval=False,note='Amostra, condições e denominadores precisam de avaliação humana. Ausência de eventos positivos não mede recall. Regras e detecção não provam autorização de acesso.')
