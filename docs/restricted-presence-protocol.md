# Presença e permanência — protocolo de confiança

Escopo inicial: uma pessoa dentro de uma área definida na imagem, com presença confirmada por 0,4 s e permanência por 10 s de observações confiáveis. Isto não detecta autorização de acesso nem identifica pessoas: a área é configurada pelo operador.

## Contrato da regra
- Centro inferior da caixa dentro do polígono; não basta a caixa encostar na área.
- Classe person; carros e outros objetos não acionam estas zonas.
- Limiar 0,45 para nascimento e confirmação; pontuação não é probabilidade de acerto.
- Caixas fracas podem manter continuidade, mas não somam permanência.
- Ausência ou observação fora da zona interrompe a soma daquele intervalo; o tempo confiável anterior continua acumulado na mesma presença enquanto não se perde o acompanhamento.
- Lacuna maior que 2 s encerra o ID como acompanhamento perdido, sem saída física comprovada. Uma nova observação recomeça confirmação.
- Permanência significa tempo observado acumulado, não presença contínua comprovada durante oclusões. Metadata observed_seconds documenta essa base; duration continua o intervalo desde a primeira observação para compatibilidade.
- Evento curto com menos de 0,4 s pode ser omitido. Ausência de registro não prova área vazia.
- IDs fragmentados podem dividir uma permanência e impedir o alerta; não fundir IDs por identidade presumida.

## Dados para treinamento e avaliação
O arquivo work/restricted-validation/dataset-template.json é um modelo vazio, não um conjunto rotulado. Não calcular aprovação com ele.

1. Obter gravações autorizadas da câmera alvo: dia, noite, iluminação variável, pessoas pequenas, bordas, oclusão, passagem rápida e períodos vazios.
2. Anotar todas as pessoas por caixa e tempo, além dos intervalos de presença na zona. Registrar oclusões e casos não verificáveis. Não usar saídas do detector como verdade de referência.
3. Conferir anotações com segunda pessoa; resolver divergências ou conservar como ambíguas.
4. Separar gravações e dias inteiros entre treino, validação e teste antes de escolher pesos/limiares. Quadros vizinhos não podem aparecer nos dois lados.
5. Treinar/fine-tunar detector somente no treino; escolher parâmetros somente na validação. Avaliar uma vez no teste reservado, incluindo cenas negativas.
6. Medir detecções por distância/iluminação, eventos perdidos, falsos alertas por hora, atraso de alerta e fragmentação de acompanhamento. Publicar denominadores, não apenas percentuais.
7. Definir metas de aprovação com a operação: custo de omissão versus falso alerta, condições cobertas e quando exigir revisão. Não declarar pronto com seis vídeos sem anotações.
8. Testar por períodos prolongados, incluindo desligamento, reconexão, sobrecarga e retenção. Conferir dados e evidências recuperáveis após reinício.

Neste marco não houve treinamento de novos pesos. Foram corrigidas regras verificáveis e criado o procedimento que permitirá avaliar o treinamento sem resultados artificiais. Os vídeos públicos existentes servem para regressão técnica, não comprovam eficácia na câmera alvo.
