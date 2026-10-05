# Treinamento de pessoas — 03/10/2026

O PC PC de desenvolvimento treinou dois candidatos YOLO11m. O sistema agora mantém o detector geral e usa o primeiro candidato como reforço **somente no escopo de pessoas**. Não é treinamento para reconhecer assalto, arma ou identidade.

## Dados e seleção

- MOT17: sequências 02/04/05 para treino, 09/10 para validação, 11/13 para teste separado. Uma variante FRCNN por sequência evita repetir as mesmas imagens das três variantes.
- Treino: 829 imagens originais, 24.339 caixas válidas de pedestres e 25 recortes de fundo sem pessoas anotadas. Validação: 119 imagens; teste inicial: 165 imagens.
- Primeiro treino: máximo 20 épocas, encerramento antecipado na época 7; checkpoint da época 2 escolhido pela validação. Resolução 960, batch 6, freeze 10, AdamW 0,0001, seed 42, CUDA. Preservação explícita da cabeça original da classe person ao reduzir 80 classes para uma.
- Segunda tentativa: 8 épocas, freeze 23, taxa 0,00002; acrescentou 126 imagens anotadas COCO de treino, amostradas com peso quatro. São 126 imagens, não 504 imagens distintas. Seleção combinou MOT e COCO de validação; checkpoint da época 1. Não superou a regra de preservação da precisão genérica.
- O primeiro candidato isolado melhorou no teste MOT17, mas regrediu no COCO. Sua substituição global foi rejeitada.
- Combinação: mantém caixas fortes do modelo geral; aceita caixas adicionais do especialista com confiança ≥0,75, sem sobreposição IoU ≥0,3 com caixas fortes. Ambos entram no mesmo ByteTrack. Detecções gerais de baixa confiança continuam disponíveis para recuperar trajetórias. Limite fixado usando exclusivamente validação antes do teste MOT20.

## Teste final separado

MOT20-01 e MOT20-03: 96 imagens amostradas a cada 30 quadros, 11.253 caixas válidas, sem treino nessas sequências e sem duplicatas exatas com as imagens originais dos outros conjuntos. São sequências públicas anotadas de treino do benchmark reservadas por nós para avaliação; não é o teste oficial MOTChallenge.

| Configuração | Acertos | Falsos positivos | Omissões | Precisão | Cobertura | F1 |
|---|---:|---:|---:|---:|---:|---:|
| Geral anterior | 1.563 | 38 | 9.690 | 97,63% | 13,89% | 0,243 |
| Geral + reforço treinado | 5.322 | 108 | 5.931 | 98,01% | 47,29% | 0,638 |

Mais 3.759 caixas corretas e ganho de 33,40 pontos na cobertura. Ainda há 5.931 omissões; falsos positivos aumentaram de 38 para 108. Esses números descrevem caixas em cenas densas, não pessoas únicas ou acerto de alertas. Quadros da mesma sequência são correlacionados.

Regressão COCO reutilizada: cobertura mantida em 73,65%; precisão 90,08% → 89,34%; falsos positivos 12 → 13. Esse recorte já havia sido visto anteriormente e não representa outro teste novo.

Correspondência IoU ≥0,5 com anotações; alvos válidos têm prioridade sobre regiões ignoradas. Falsos positivos sobre regiões ignoradas são desconsiderados por interseção/área da predição ≥0,5. A métrica principal mantém pessoas muito ocluídas. É um protocolo local de detecção, não mAP/MOTA/HOTA oficial ou avaliação de interpretação criminal. Não podemos garantir ausência de imagens desses benchmarks no pré-treino original do fabricante.

## Integração e reprodução

Pesos ativos: `models/yolo11m.pt` e `models/sentinel-person-mot17-v1.pt`. SHA256 do reforço: `96745717c9df2fc3260a72bad90724e316a034ddefe4f5596504565ef7d8d212`.

Configuração local: `PERSON_SPECIALIST_MODEL_NAME` aponta para os pesos e `PERSON_SPECIALIST_THRESHOLD=0.75`. Para reverter o reforço, deixar o caminho vazio e reiniciar o Sentinel em uma janela sem entrada ativa. O detector geral continua sendo o mesmo.

Scripts, listas, anotações, logs, checkpoints e decisões estão em `<pasta-do-projeto>/work/person-training` e scripts correspondentes em `<pasta-do-projeto>/work`. `train_person.py`, `train_mixed_person.py`, `evaluate_trained_person.py`, `validate_person_fusion.py`, `test_frozen_fusion.py` e `validate_trained_videos.py` registram o processo. Use novas pastas de execução ao repetir; não use os testes já consultados para alegar nova validação independente.

O reforço custa aproximadamente 54 ms/quadro nas 96 imagens, contra 30 ms do geral sozinho, sem pose/eventos. A reprodução do vídeo original é independente. Não há promessa de inferência a 60 FPS.

Para uso real faltam gravações da câmera alvo com anotações revisadas, taxa de falsos alertas por hora, oclusões/baixa luz, avaliação temporal de tracking e avaliação das respostas visuais com referência humana. ROI operacional ainda não foi medido. A combinação foi aprovada para este protótipo, não certificada para segurança.

Fontes: [MOT17](https://motchallenge.net/data/MOT17/), [MOT20](https://motchallenge.net/data/MOT20/), [treinamento Ultralytics](https://docs.ultralytics.com/modes/train/), [fine-tuning](https://docs.ultralytics.com/guides/finetuning-guide/). Avaliar licenças dos dados e pesos antes de redistribuição/uso comercial; não redistribuímos as imagens nesta entrega.
