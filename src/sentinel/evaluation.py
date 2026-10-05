"""Paired pilot summary: preserve failures, never invent monetary savings."""
from statistics import median
def trial_summary(rows):
    paired={}
    for row in rows:paired.setdefault(row['task_id'],{})[row['mode']]=row
    pairs=[x for x in paired.values() if 'manual' in x and 'sentinel' in x]
    counts={mode:sum(x[mode]['outcome']=='correct' for x in pairs) for mode in ['manual','sentinel']}
    savings=[(x['manual']['seconds']-x['sentinel']['seconds'])/60 for x in pairs]
    return dict(pairs=len(pairs),correct=counts,median_minutes_saved=round(median(savings),3) if pairs else None,
                suitable_for_estimate=len(pairs)>=10 and counts['manual']==len(pairs) and counts['sentinel']==len(pairs),
                note='Tempos incluem pares com falhas. Dez pares corretos são um início de piloto, não garantia estatística nem economia comprovada para a empresa. Custos e conferência devem entrar no cálculo; valores negativos indicam mais tempo com o sistema.')
