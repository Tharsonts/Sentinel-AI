# Demonstração visual

Gravação de teste `people-detection.mp4` do repositório público Intel IoT DevKit sample-videos, processada no Sentinel em 04/10/2026. SHA256: `18ffe8672d741e3e29c9d891d22c59d453720b086c25b35c88b393d55f92f693`.

Foram processados 596 quadros de um vídeo de aproximadamente 49,7 segundos a 12 FPS. As caixas e poses salvas acompanham o tempo do vídeo; os rastros mostram os três segundos anteriores de posições observadas. Uma caixa não representa identidade, intenção ou objeto na mão.

O GIF do painel foi capturado diretamente no navegador, com reprodução das detecções salvas e a resposta real da visão geral ao lado. A resposta foi produzida depois do processamento, usando 12 imagens distribuídas no vídeo; não é uma resposta nova da IA a cada quadro do GIF.

Eventos desta execução: {"track_lost": 5, "zone_enter": 7, "zone_exit": 2}. Eventos de perda de tracking e fim da fonte podem não possuir imagem; não são evidências de saída física. O filtro aplicado muda os eventos apresentados.

Foram adicionados testes para isolamento de sessões, paginação de detecções, separação entre imagem crua e anotada e autenticação da API de replay.

Fontes: [amostras Intel](https://github.com/intel-iot-devkit/sample-videos), [licença e avisos do repositório de origem](https://github.com/intel-iot-devkit/sample-videos/blob/master/LICENSE). A gravação completa não foi adicionada ao GitHub. Os GIFs e capturas ilustram funcionamento de um teste; não comprovam precisão operacional.

## Perfil ampliado e teste de trânsito

O perfil local anterior reconhecia somente pessoas. Foi trocado para pessoas, veículos e itens, preservando o reforço de pessoas. Em nova execução do vídeo `person-bicycle-car-detection.mp4`, 647 quadros foram processados sem erro. Houve 106 observações de carro, 65 de bicicleta, 228 de pessoa e 7 classificações de celular. São observações repetidas ao longo de quadros, não contagens de objetos únicos nem medidas de acerto; as classificações de celular precisam de revisão visual.

A exibição usa oito cores estáveis por ID temporário, caminhos de até seis segundos e retenção do último rastro por até três segundos, sem uma caixa fantasma. Cores podem repetir e tracking pode trocar IDs durante oclusões. Não é reconhecimento de identidade. O GIF acima registra a versão anterior das cores.

95 testes de software passaram. A seleção de uma imagem em 4 segundos foi verificada na API: análise do intervalo de 1 a 7 segundos. Estes resultados não validam furto, objetos pequenos, cenas lotadas ou precisão em supermercados.

## Evolução para prateleiras

Uma retirada de item exige definir a região da prateleira, acompanhar mão e item no tempo e conferir eventual retorno. Proximidade ao punho não comprova posse. Produtos desconhecidos não são automaticamente reconhecidos como objeto genérico. Antes de ativar alertas, é necessário coletar exemplos consentidos de retirada, devolução, reposição e oclusão, separar câmeras para validação e medir falsos alertas por hora e ações perdidas. Essa funcionalidade permanece proposta, não implementada ou treinada neste protótipo.
