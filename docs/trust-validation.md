# Sentinel — cinco etapas de avaliação e confiança

Rodada posterior: [treinamento real de pessoas e combinação ativa](person-training.md). Este documento abaixo preserva os resultados da rodada anterior à produção dos pesos treinados.

03/10/2026 · PC de desenvolvimento · <pasta-do-projeto> · servidor principal único na porta 8000. Notebook permaneceu desligado. Esta rodada avançou avaliação e regras; não produziu pesos treinados para a câmera alvo.

## Situação das cinco etapas

| Etapa | Entrega desta rodada | Pendência para uso real |
|---|---|---|
| 1. Critérios e falhas | Regras explícitas; contagem de acertos, falsos alertas, omissões e atrasos; correção de ID reaparecendo após ausência | Aprovar metas com a operação, conforme custo de cada erro |
| 2. Referência separada | Imagens COCO anotadas: 64 para calibração e 64 novas para teste, fixadas antes da execução | Gravações completas da câmera alvo anotadas; revisão independente das anotações |
| 3. Ajuste e comparação | Dois modelos, quatro limiares; escolha congelada antes do teste; manutenção do modelo atual após comparação | Fine-tuning somente quando houver conjunto de treino da câmera alvo |
| 4. Fluxo e regressão | 79 testes; seis vídeos completos; sequência sintética; servidor e análise visual conferidos | Câmera RTSP real, baixa luz, piloto prolongado e taxas de alertas contra anotações temporais |
| 5. Relatório | Resultados, critérios, scripts e limitações documentados | Aprovação operacional continua pendente; não há certificação de segurança |

Não confundir a conclusão da rodada técnica com conclusão do treinamento específico ou validação de produção.

## Comparação exclusiva de pessoas

Conjunto de calibração: os primeiros 64 IDs crescentes de COCO val2017, já separados para seleção. Candidatos YOLO11m e YOLO26m; limiares 0,30, 0,45, 0,60 e 0,75. Inferência de pessoas em 1280 px e correspondência por classe/IoU ≥ 0,5. Tratamento de multidões é simplificado, e estas métricas não são mAP.

Antes do teste, fixei alvos exploratórios de precisão ≥85% e cobertura ≥60% na validação, escolhendo maior cobertura entre candidatos elegíveis. Esses limites são critérios de triagem técnica em imagens genéricas, não metas adequadas já aprovadas para segurança. A escolha foi YOLO26m/0,45.

Teste novo: os IDs de posições 128 a 191 em ordem crescente, 64 imagens ainda não usadas nos testes anteriores. Ambos os modelos foram comparados com as mesmas anotações, contendo 148 caixas de pessoas não marcadas como multidão.

| Modelo / limiar | Acertos | Falsos positivos | Omissões | Precisão | Cobertura | F1 |
|---|---:|---:|---:|---:|---:|---:|
| Atual: YOLO11m / 0,45 | 109 | 12 | 39 | 90,08% | 73,65% | 0,810 |
| Candidato: YOLO26m / 0,45 | 106 | 12 | 42 | 89,83% | 71,62% | 0,797 |

O candidato cumpriu os alvos exploratórios absolutos, mas não superou o atual: perdeu mais pessoas com os mesmos 12 falsos positivos. Portanto não foi ativado. Não ajuste de novo o limiar usando esse teste: ele deixa de ser reservado quando é usado para escolher a próxima tentativa.

O modelo ativo permanece YOLO11m, confiança 0,45. Agora o painel oferece modo Pessoas · presença e permanência, ativo por padrão na configuração local, com uma categoria. Outros escopos permanecem disponíveis. Zonas continuam com classes person, preservando polígonos e duração.

90,08% é precisão de caixas nesse recorte de imagens, não probabilidade de um alerta estar certo em uma empresa. Houve 39 pessoas anotadas não detectadas. A amostra não representa todas as câmeras, baixa luz ou objetos escondidos. Separação do nosso processo de escolha não prova independência dos dados usados no pré-treinamento. Não há motivo para afirmar melhora de precisão nesta rodada; houve uma comparação que evitou uma troca sem benefício.

## Correção nova nas regras

Um ID podia reaparecer após uma ausência maior que o timeout e herdar a presença anterior quando outras atualizações mantinham o relógio do motor ativo. Agora o estado antigo expira antes de processar o ID que voltou. O sistema registra perda de acompanhamento sem confirmar saída e exige nova confirmação de presença.

Permanência exige observações fortes dentro da zona. O tempo suportado anteriormente pode acumular dentro da mesma presença, mas períodos não observados não somam. Fragmentação de IDs ainda pode dividir uma presença. A regra não confirma autorização nem identidade de pessoas.

## Avaliador de acontecimentos

Scripts evaluate_presence.py e export_presence_predictions.py preparados no diretório scripts. Exportação usa o tempo relativo das imagens do arquivo, não o horário de parede e não IDs presumidos de pessoas. Sessões antigas sem referência temporal precisam ser reprocessadas.

O avaliador compara eventos com janelas temporais anotadas e zona, em correspondência um a um. Duplicatas contam como falsos alertas; eventos anotados ausentes contam como omissões. A correspondência busca o maior número de pares válidos, evitando um acerto escolhido cedo bloquear outro possível.

Exige revisão manual completa da gravação. Rejeita conjunto vazio, origem compartilhada entre treino e teste, previsões ausentes para uma gravação e tempos inválidos. Use lista vazia para registrar que nenhuma previsão ocorreu, permitindo medir omissões. Intervalos não verificáveis são separados e não entram como tempo negativo; sobreposições são unidas para não descontar tempo duas vezes. Uma referência sobreposta a esses intervalos é rejeitada para ser corrigida.

Resultados: acertos, falsos alertas, omissões, precisão, cobertura, horas revisadas, falsos alertas por hora e atraso mediano em relação ao instante de referência. Se não houver eventos positivos, cobertura permanece indefinida em vez de aparecer como 100%. Não gera aprovação operacional automática.

O template de referência está vazio, com exemplo de estrutura claramente marcado. Não foram inventadas anotações temporais para os vídeos de assalto/acidente. Portanto ainda não há medição real de falsos alertas por hora nesses vídeos.

## Testes

79 testes passaram com duas advertências de dependências. Casos novos cobrem referências incompletas, vazamento de origem entre splits, duplicatas, eventos perdidos, cenas negativas, regiões ambíguas, exportação no tempo do vídeo, modo de pessoas e retorno de ID antigo.

Seis vídeos processados integralmente, total de 2.875 quadros: Robbery048, Robbery050, RoadAccidents001, RoadAccidents002, demo-h264 e intel-people. Contagens de eventos mudaram em um vídeo após o modo exclusivo de pessoas e correção de estado; sem anotação completa, contagem menor não pode ser chamada de redução comprovada de erros.

A cena noturna continuou sem detecções. Essa falha conhecida impede apresentar o sistema como confiável em qualquer condição. O teste de vídeo não é equivalente a validar uma câmera real com sua rede, codec e iluminação.

Sequência sintética: 72.000 quadros negativos sem alerta; 100 ciclos positivos com 100 entradas, 100 permanências e 100 saídas; estado interno vazio ao final. A execução foi simulada rapidamente, não duas horas físicas de vigilância, e não mede precisão de imagens reais.

Servidor principal: 719 quadros, autenticação, vídeo com HTTP 206, análise visual pronta com 12 imagens e apenas porta 8000 entre portas Sentinel. UI conferida com modo de pessoas ativo e modelo YOLO11m. Análise visual permanece auxiliar, sem áudio e baseada em amostras.

## Próxima dependência concreta

Para treinar para o local de uso, precisamos de gravações autorizadas daquela câmera, anotadas por caixa e intervalo, com condições variadas e períodos vazios. Os vídeos públicos disponíveis serviram à regressão, mas não fornecem automaticamente verdade de referência da área que configuramos.

Separar gravações/dias de origem entre treino, validação e teste. Treinar apenas no treino, escolher parâmetros apenas na validação e publicar resultados no teste reservado. A presença de anotações públicas de caixas permite esta comparação de detectores; não fornece anotações temporais de permanência para os nossos vídeos.

Sem essa etapa, não iniciar fine-tuning usando previsões da própria IA como rótulos confiáveis. Isso pode reforçar seus erros e dar uma aparência enganosa de precisão. O sistema hoje está mais testável e corrigiu falhas de estado; confiança operacional continua por demonstrar.

Referências: [COCO](https://cocodataset.org/) e [anotações públicas utilizadas](https://huggingface.co/datasets/merve/coco/blob/main/annotations/instances_val2017.json). Dados detalhados e política de seleção estão em Sentinel-confianca-metricas.json; scripts e imagens em <pasta-do-projeto>/work/restricted-validation e <pasta-do-projeto>/work/precision.
