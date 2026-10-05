"""Constrained search phrases. Never translate arbitrary text into SQL."""
import re,unicodedata

def interpret(query):
    text=''.join(c for c in unicodedata.normalize('NFD',query.lower()) if not unicodedata.combining(c)).strip()
    patterns={
        'person':r'\bpessoas?\b', 'car':r'\bcarros?\b', 'motorcycle':r'\bmotos?\b',
        'bicycle':r'\bbicicletas?\b', 'bus':r'\bonibus\b', 'truck':r'\bcaminh(?:ao|oes)\b',
    }
    objects=[name for name,pattern in patterns.items() if re.search(pattern,text)]
    kinds=[]
    for kind,pattern in [('zone_enter',r'\b(?:entrada|entradas|entrou|entraram)\b'),
                         ('zone_exit',r'\b(?:saida|saidas|saiu|sairam)\b'),
                         ('zone_dwell',r'\b(?:permanencia|permanencias)\b'),
                         ('track_lost',r'\brastreamento perdido\b')]:
        if re.search(pattern,text):kinds.append(kind)
    if len(objects)>1 or len(kinds)>1:raise ValueError('Pesquise um tipo de objeto e um acontecimento por vez.')
    base=re.search(r'\b(?:eventos?|acontecimentos?|registros?)\b',text)
    if not objects and not kinds and not base:raise ValueError('Use os filtros ou exemplos: "entradas de pessoas", "permanência de pessoas", "saídas de carros".')
    # Reject interpretations that would silently ignore unsupported criteria.
    residue=text
    for pattern in [*patterns.values(),r'\b(?:entrada|entradas|entrou|entraram|saida|saidas|saiu|sairam|permanencia|permanencias)\b',r'\brastreamento perdido\b',r'\b(?:eventos?|acontecimentos?|registros?)\b',r'\b(?:mostre|mostrar|buscar|busque|encontrar|encontre|de|da|do|das|dos|uma|um|as|os|a|o|com|registrada|registradas|prolongada|prolongadas)\b']:
        residue=re.sub(pattern,' ',residue)
    if re.sub(r'[\s.,?!]','',residue):raise ValueError('Essa frase contém critérios ainda não suportados. Use os filtros de câmera, zona, data e duração; não interpretamos intenção, identidade ou aparência.')
    return dict(object_type=objects[0] if objects else None,event_type=kinds[0] if kinds else None)
