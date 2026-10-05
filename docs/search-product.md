# Sentinel AI — busca de acontecimentos com evidências

## Problema e público inicial

Hipótese: operadores de portaria, supervisores de condomínios e pequenas operações de segurança gastam tempo procurando acontecimentos e reunindo registros. O protótipo pretende permitir localizar um evento definido por câmera, zona, intervalo, objeto e duração registrada, conferir sua imagem e gerar resumo/relatório do mesmo recorte.

O usuário inicial é quem revisa registros; não é necessário que seja instalador ou especialista em IA. A adoção e o ganho de tempo ainda não foram medidos com usuários. Não há evidência de que uma empresa específica precise desta solução ou de que a novidade seja exclusiva.

Busca por vídeo/eventos já existe em produtos comerciais. XProtect reúne busca por movimento, alarmes e metadados (https://www.milestonesys.com/articles/finding-video-evidence-in-XProtect/). O Grupo Pro Security divulga o COP360 com integração de pessoas, tecnologia e IA (https://prosecurity.com.br/cop-360/). O valor deste portfólio é demonstrar uma implementação funcional, explicável e integrada em duas máquinas, com escopo delimitado.

## Entrega desta versão

- Servidor PC confirmado: PC de desenvolvimento; aplicação em <pasta-do-projeto>, API na porta 8000. Notebook confirmado pelo chat remoto: DESKTOP-MCO03LC, cliente em D:/SentinelAI-Client.
- Painel: Buscar acontecimentos, Ao vivo, Configurações.
- Filtros de dia, intervalo, câmera, zona, objeto, tipo de evento e duração registrada mínima, com paginação e quantidade exata de resultados.
- Horários digitados no fuso do navegador convertidos para UTC; início incluído e fim excluído. Seleção de um dia usa a meia-noite do dia seguinte como fim.
- Frases simples restritas: entradas de pessoas, permanência de pessoas, saídas de carros, rastreamento perdido. Não se promete interpretação livre: critérios não suportados ou conflitantes retornam erro explícito. Nenhum LLM gera SQL.
- JPEG anotado salvo no SQLite junto ao evento, na mesma transação. A evidência não é o último frame atual e não é reconstruída para registros antigos.
- Evidências exigem autenticação; a chave não entra em URL e respostas JPEG usam Cache-Control: no-store.
- A busca não depende de LLM. Resumo sem IA, consulta local e relatório utilizam os mesmos filtros. LLM recebe registros estruturados, nunca JPEGs; detalhes limitados a 24 eventos recentes para caber no contexto local, com contagens de todos os resultados e aviso de truncamento.
- Compatibilidade com cliente push anterior preservada. Clientes novos enviam X-Camera-ID e X-Session-ID; checagem sob lock rejeita imagens de outra câmera/sessão com 409 antes de inferência.
- Cliente remoto atualizado para reconexão com backoff, envio sequencial, cancelamento e recuperação somente da própria sessão. Nenhuma webcam foi aberta durante esta entrega.

## Limites concretos

Evidência inicial é imagem JPEG no momento de entrada/permanência/saída detectada, não clipe nem gravação contínua. Eventos sem frame novo (perda de tracking e encerramento) não recebem evidência inventada. Imagens são quadros anotados de apoio à revisão, não um mecanismo de certificação da imagem original.

Duração é medida quando cada evento é registrado. Permanência é emitida uma vez ao atingir o limite da zona; uma visita longa em curso não atualiza esse registro continuamente. Buscar >=20s pode encontrar eventos posteriores de saída/perda/fim, mas não atualizar automaticamente um evento emitido aos 10s. Histórico com duração contínua por visita é uma evolução, não algo validado nesta entrega.

Contamos eventos, não indivíduos únicos. Ausência de evento não prova ausência de atividade: enquadramento, falha da fonte e falta de detecção podem explicar isso. Uma sessão running apenas indica processamento preparado; receiving indica frame recente.

Uma câmera ativa por servidor. RTSP implementado, ainda sem câmera IP real validada. Não há reprocessamento retroativo de todo vídeo, busca por roupas/identidade/intenção, gravação de áudio, cobertura certificada, inicialização automática com Windows ou política automática de retenção. Eventos e JPEGs permanecem no banco, cuja ocupação deve ser acompanhada durante uso prolongado. A configuração de zonas ainda é avançada; editor visual e assistente de calibração são próximos passos.

## Roteiro demonstrável sem webcam

O teste isolado work/validate_search_live.py inicia uma instância somente localhost, porta 18001, banco work/search-validation/events.db e zona de demonstração. Usa o vídeo sintético existente demo-bus.avi, portanto serve para integração e GPU, não para medir precisão real. Os dados não entram no banco principal. O script deixa a instância ativa para QA visual e precisa ser encerrado após o teste.

O teste trouxe quatro eventos de permanência de pessoas, imagens autenticadas e resposta do LLM. UI mostrou resultados, evidência correspondente, resumo filtrado, busca sem resultado para duração >=20s e rejeição de 'pessoas suspeitas'. Nenhum evento artificial foi inserido no histórico NOTEBOOK_01.

## Próxima validação com usuários

Usar vídeos representativos com consentimento e situações anotadas por uma pessoa. Para 10 tarefas de localizar acontecimentos, comparar revisão manual com a busca: tempo até encontrar o registro correto, acerto dos resultados, eventos perdidos, falsos eventos e facilidade de uso. Medir também reconexão, atraso, CPU/GPU e armazenamento por hora. Não declarar redução de tempo antes desse experimento.

Na próxima demonstração com notebook: atualizar a página local do cliente, parar voluntariamente o processamento antes de configurar zona de imagem inteira, salvar a zona e iniciar o envio pelo notebook. Permanecer por mais de 10s, buscar permanência de pessoas em NOTEBOOK_01, abrir a imagem e pedir um resumo. A câmera pode ser testada com a pessoa sentada; não é preciso sair do quarto. Não alterar zonas enquanto outra pessoa estiver usando a fonte.
