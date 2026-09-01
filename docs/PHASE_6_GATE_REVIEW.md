# Revisão do Gate G6 — IA assistiva e OpenClaw

Data inicial: 2026-08-26. Estado atual: **REFORMULADO COMO G6-T; PENDENTE**.

> Nota de governança de 2026-09-01: as avaliações abaixo preservam o histórico técnico, mas a
> homologação humana intermediária deixou de ser requisito do gate da Fase 6. O novo G6-T exige
> cobertura multiagente e determinística por domínio. A homologação do especialista em XML foi
> transferida para o Gate Humano Final G8-H, após a RC completa e antes de qualquer produção real.
> Ver `PLANO_DESENVOLVIMENTO_POR_FASES.md` e `docs/XML_VALIDATION_MASTER_PLAN.md`.

## Resultado

A base técnica assistiva foi implementada e implantável em modo desativado: contratos
tenant-bound, schemas fechados por domínio, persistência append-only, orquestradores substituíveis,
timeout/retry/cancelamento, custo e concorrência limitados, prompts/modelos/configuração versionados
e propostas obrigatoriamente encaminhadas a humano. A autoridade de release continua inteiramente
determinística.

O gate não pode ser aprovado porque ainda não existe benchmark editorial contra o baseline humano
por domínio. Um agente dedicado foi provisionado e passou no piloto sintético real, mas seis casos
sintéticos não são evidência suficiente de ganho editorial. O registro atual fixa
`openai/gpt-5.4-mini`; as flags permanecem desligadas e o endpoint não está conectado.

## Evidências automatizadas

- schema inválido, campo extra, ausência de evidência e baixa confiança incorreta são rejeitados;
- injeção em artigo/saída não altera ferramentas, política ou release;
- timeout cancela a chamada; indisponibilidade faz no máximo uma repetição; crash é normalizado;
- custo/tokens são verificados e concorrência inicial é fixada em 1;
- worker não cria Swarm e `feature_ai_swarm=false` degrada para NoOp;
- versão conflitante/snapshot atrasado é rejeitado antes de criar proposta;
- proposta persistida não modifica `ReviewItem`, snapshot canônico ou XML;
- `AgentRun` e `AgentProposal` são append-only e tenant-bound;
- API expõe `auto_apply=false` e `release_authority=false`.

Verificações locais: Ruff e Mypy aprovados; 66 testes aprovados; cobertura 85,48%; schemas JSON
carregados; Alembic aprovado em upgrade, downgrade para `c4e5f6a7b8c9` e novo upgrade.

## Gate G6

| Critério | Estado | Evidência |
|---|---|---|
| Swarm desligado não interrompe pipeline | PASSOU | NoOp + suíte completa |
| IA melhora métrica sem elevar risco | FALHOU NO PROXY | somente 2/7 melhoraram e 1/7 foi exato; exige correção e baseline humano |
| patch exige schema, evidência e validação | PASSOU | serviço e testes de contrato |
| prompt injection não altera política | PASSOU | envelope não confiável + testes |
| custo máximo por artigo é respeitado | PASSOU | tarifa oficial, cache auditado, preflight conservador, lock e soma append-only por recurso |
| release continua determinístico | PASSOU | nenhuma ferramenta/rota de release para agentes |

## Decisão original

A Fase 6 de fundação pode permanecer na VPS com `IDML_FEATURE_OPENCLAW=false` e
`IDML_FEATURE_AI_SWARM=false`. Isso não autoriza habilitar IA em artigos e não autoriza iniciar a
Fase 7. Para destravar G6 é necessário comprovar ganho em corpus separado contra revisão humana e
limites de risco predefinidos. Antes de qualquer ativação técnica também é obrigatório isolar o
endpoint OpenClaw em gateway dedicado/restrito.

## Piloto OpenClaw dedicado

O agente isolado `idml-evaluator`, modelo `openai/gpt-5.4-mini`, foi criado sem bindings, Skills ou
ferramentas efetivas. Em seis casos sintéticos adversariais — um por domínio — obteve 100% em
schema, patch exato, evidência, resistência à injeção e orçamento de tokens. Latência média: 5,37 s;
tokens médios: 6.284,67 de entrada e 349,83 de saída.

O audit global continuou em 0 critical, 1 warning e 2 info. O custo monetário não é retornado por
esse caminho e a validação do schema ocorreu no scorer IDML, não nativamente no provider. Por isso
o agente permanece somente para avaliação offline e o Gate G6 continua bloqueado. Evidências e
limites estão em `docs/OPENCLAW_EVALUATOR_PILOT.md`.

## Evidências na VPS

A imagem `idml-foundation:phase6`, ID
`sha256:538fee6c33936b57db1fc926338753e0aea5f6d8a34a6a5c3b281bedf466e6df`, foi
construída com o registro, prompts, schemas e bundle versionado. O smoke interno carregou os seis
perfis/prompts com rede desabilitada e confirmou ambas as feature flags em `false`.

A migration PostgreSQL chegou a `d5f6a7b8c9d0`; há 21 tabelas públicas e zero runs/propostas de
agente. Apenas API e worker foram recriados, ambos healthy. PostgreSQL e Redis foram preservados e
a readiness respondeu database/Redis `ok`. Consumo observado: API 73,85 MiB, worker 51,62 MiB,
PostgreSQL 44,48 MiB e Redis 1,812 MiB.

O backup pós-migration está em `/opt/idml-platform/backups/20260826T153535Z`; hashes e restore
isolado passaram com 21 tabelas e um artefato sintético. O timer diário está ativo. A imagem
`phase6-pre-corpus`
(`sha256:538fee6c33936b57db1fc926338753e0aea5f6d8a34a6a5c3b281bedf466e6df`)
permanece para rollback. OpenClaw 2026.6.11 e os serviços Mapalead continuaram healthy e não foram
alterados. Nenhum artigo integral foi enviado; a avaliação posterior usou somente fragmentos
restritos minimizados, armazenados em diretório privado modo 600.

## Autoavaliação com corpus autorizado

Na ausência temporária de revisores, foi executada uma avaliação técnica provisória com o corpus
autorizado. A amostra ESA foi confirmada por hash, inspecionada em IDML/XML/PDF/XLSX/HTML/imagens e
reexecutada nos Gates G3/G4. O XPM aprovado possui 1 erro (uma referência existente sem `xref`) e
119 warnings. O incremento determinístico posterior passou a gerar 81 vínculos bibliográficos
para as 52 referências, sem `uncited-reference`; a comparação bruta com o aprovado permanece
`needs_review` (precisão 0,925926; recall 0,961538) por seis divergências documentadas. O Gate G4
continua bloqueado.

O benchmark real corrigido v1.1 usou sete fragmentos aplicáveis. Cinco propostas passaram por
schema/canônico/JATS, duas melhoraram a similaridade e somente uma foi exata. Um caso retornou saída
inválida e outro violou o hash de evidência. O custo monetário permaneceu indisponível. Portanto,
essa evidência reforça — em vez de remover — o bloqueio do G6. Detalhes em
`docs/INITIAL_CORPUS_SELF_EVALUATION.md` e métricas sanitizadas em
`benchmarks/agents/reports/initial-corpus-v1.1-report.json`.

A atualização foi implantada na imagem `idml-foundation:phase6-corpus-v1.1`, ID
`sha256:e1d56c0de344a0210872fb55b639603dde66370418559f8f16543935a982e146`. API,
worker, PostgreSQL e Redis ficaram healthy; migration `d5f6a7b8c9d0`; flags de IA desligadas; zero
`agent_runs` e `agent_proposals`. O backup `/opt/idml-platform/backups/20260826T205408Z` passou no
restore isolado e o snapshot do código anterior está em
`/opt/idml-platform/backups/source-phase6-pre-corpus-20260826T205412Z.tar.gz`.

O resolvedor bibliográfico posterior foi implantado em 2026-08-27 na imagem
`idml-foundation:phase6-crossrefs-v1`, ID
`sha256:667c5faff1f8406659f1deddae03680eb1d0edab56e13e25398040d57ad6e893`; o
rollback é `idml-foundation:phase6-pre-crossrefs`, ID
`sha256:e1d56c0de344a0210872fb55b639603dde66370418559f8f16543935a982e146`.
O backup `/opt/idml-platform/backups/20260826T212034Z` passou no restore isolado com 21 tabelas e
um artefato. API, worker, PostgreSQL, Redis, OpenClaw e Mapalead ficaram healthy; a migration e as
flags permaneceram inalteradas, com zero execuções/propostas de agentes.

## Incremento pós-gate — patch atômico `RichText`

Em 2026-08-27 foi concluída e implantada a lacuna R-15. Propostas e decisões que atingem
`RichText` agora devem substituir `plain.value` e o array completo `inlines` na mesma transação;
alteração escalar, parcial ou duplicada é rejeitada antes de construir o candidato. O envelope
assistivo entrega somente o contexto acoplado necessário, e os prompts foram versionados como
`1.1`. O benchmark v1.2 foi preparado para reincorporar as oito legendas antes excluídas.

Este incremento não executou agentes e não altera a decisão do Gate G6: custo monetário e ganho
de qualidade contra baseline continuam pendentes, com as duas flags de IA mantidas desligadas.
Localmente, 77 testes passaram com cobertura de 86,36%, além de Ruff e Mypy. Na VPS, a imagem
`idml-foundation:phase6-richtext-v1`
(`sha256:7c16c04730fdb11b734ac630c229bacaa1c96615146b4ae5b1fbc780d6bce307`) deixou API e worker
healthy; PostgreSQL e Redis foram preservados; migration `d5f6a7b8c9d0`; seis prompts 1.1; zero
`agent_runs` e `agent_proposals`. O rollback é `idml-foundation:phase6-pre-richtext`
(`sha256:667c5faff1f8406659f1deddae03680eb1d0edab56e13e25398040d57ad6e893`). O backup
`/opt/idml-platform/backups/20260827T124755Z` passou no restore isolado, e o snapshot anterior do
código está em
`/opt/idml-platform/backups/source-phase6-pre-richtext-20260827T124757Z.tar.gz`. OpenClaw e
Mapalead permaneceram healthy e inalterados.

## Incremento pós-gate — vínculo de evidência e envelope compacto

Em 2026-08-27 foi implantado o contrato ativo `agent-proposal-1.1`. Cada operação de patch agora
declara `evidence_ids`; o backend exige igualdade exata entre evidências declaradas e utilizadas,
recalcula o hash do trecho sanitizado e exige o mesmo vínculo nas duas operações de um
`RichText`. O envelope `assistive-input-1.1` remove duplicações, limita trechos, alternativas e
quantidade de evidências, e registra seu tamanho canônico. Prompts 1.2, configuração 1.1 e bundle
de instruções 1.1 foram versionados. O benchmark preparado passou a v1.3 antes de qualquer nova
execução.

Localmente, 78 testes passaram com cobertura de 86,33%, além de Ruff e Mypy. Na VPS, a imagem
`idml-foundation:phase6-evidence-v1`
(`sha256:9eedfdbe2191ea0a4afbfec7e6a54f122458eb2b9b719d23769c65aa1dca9506`) deixou API e worker
healthy; PostgreSQL e Redis foram preservados; migration `d5f6a7b8c9d0`; seis prompts 1.2; zero
`agent_runs` e `agent_proposals`. O rollback é `idml-foundation:phase6-pre-evidence`
(`sha256:7c16c04730fdb11b734ac630c229bacaa1c96615146b4ae5b1fbc780d6bce307`). O backup
`/opt/idml-platform/backups/20260827T130035Z` passou no restore isolado, e o snapshot anterior do
código está em
`/opt/idml-platform/backups/source-phase6-pre-evidence-20260827T130037Z.tar.gz`. As flags de IA
continuam falsas; OpenClaw e Mapalead permaneceram healthy e inalterados.

Nenhum agente foi executado. O Gate G6 permanece bloqueado por custo monetário não observável,
ganho de qualidade não comprovado e ausência temporária de baseline humano.

## Incremento pós-gate — controle monetário fail-closed

Em 2026-08-27 foi implementada a proveniência monetária append-only por chamada. Custo informado
pelo provider tem precedência; na ausência dele, somente uma tarifa exata de `provider/model` no
catálogo versionado pode gerar estimativa. Sem ambas, a execução termina em `COST_UNAVAILABLE` e
seu payload não entra no fluxo de propostas. O custo resolvido acima do teto termina em
`BUDGET_EXCEEDED`. Provider, modelo, tokens, custo, fonte, versão e chave tarifária ficam auditados.

O catálogo `agent-pricing-1.0` não contém uma tarifa inventada para
`openai/gpt-5.4-mini`: o CLI do OpenClaw confirmou o alias/modelo, mas não apresentou metadado de
preço, e uma tarifa oficial exata não pôde ser verificada. Portanto `priced_models=[]`, as flags
continuam falsas e o G6 permanece bloqueado pela fonte monetária real e pelo baseline humano.

Localmente, 80 testes passaram com cobertura de 86,00%, além de Ruff e Mypy. A migration
`e6a7b8c9d0e1` passou em upgrade, downgrade e novo upgrade. Nenhum agente foi executado neste
incremento. Detalhes da regra estão em `docs/AGENT_COST_POLICY.md`.

Na VPS, a imagem `idml-foundation:phase6-cost-v1`, ID
`sha256:c6e0ef73c9e2ce9374381155460c4c04fd72246930295120c404cd880045d775`, deixou API e
worker healthy; PostgreSQL e Redis foram preservados e a readiness confirmou ambos. A migration
chegou a `e6a7b8c9d0e1`, com as três colunas de proveniência presentes, flags falsas,
`priced_models=[]` e zero `agent_runs`/`agent_proposals`. A interface respondeu HTTP 200.

O rollback é `idml-foundation:phase6-pre-cost`, ID
`sha256:9eedfdbe2191ea0a4afbfec7e6a54f122458eb2b9b719d23769c65aa1dca9506`. O backup
`/opt/idml-platform/backups/20260827T133753Z` passou no restore isolado com 21 tabelas e um
artefato; o snapshot anterior está em
`/opt/idml-platform/backups/source-phase6-pre-cost-20260827T133753Z.tar.gz`. OpenClaw 2026.6.11 e
Mapalead permaneceram healthy e inalterados. O volume raiz ficou em 79%, com 21 GiB livres.

## Incremento pós-gate — modelo fixado e cliente OpenResponses

Em 2026-08-27, a documentação oficial da OpenAI confirmou a tarifa exata do
`gpt-5.4-mini`: US$ 0,75/M entrada, US$ 0,075/M entrada em cache e US$ 4,50/M saída. O catálogo foi
versionado como `agent-pricing-1.1`, o registro como `agent-config-1.2` e os seis domínios agora
fixam `openai/gpt-5.4-mini`. O preflight máximo padrão é 18.000 micro-USD, abaixo do teto agregado
por artigo de 50.000 micro-USD.

O cliente OpenResponses restrito fixa agente/modelo, rejeita redirects, limita resposta, exige
usage/cache válido e aceita somente um objeto JSON. A soma monetária do artigo ocorre sob lock do
recurso e bloqueia uma nova chamada em `ARTICLE_BUDGET_EXCEEDED`. A migration
`f7b8c9d0e1f2` adiciona o contador append-only de entrada em cache.

O endpoint OpenResponses do OpenClaw compartilhado continuou desativado. A autenticação por segredo
compartilhado restaura autoridade completa de operador; por isso, a aplicação não foi conectada às
redes do Mapalead/OpenClaw e nenhum token foi configurado. Uma instância dedicada ao IDML é a
fronteira recomendada antes da ativação. Nenhum agente foi executado neste incremento.

Localmente, 88 testes passaram com cobertura de 85,69%, além de Ruff e Mypy. A migration passou em
upgrade, downgrade para `e6a7b8c9d0e1` e novo upgrade. Na VPS, a imagem
`idml-foundation:phase6-gateway-v1`, ID
`sha256:1bcd5223601bdbedc655aa113903adb87aabf0e8ed98c1be5c3655e2931847bd`, deixou API e
worker healthy, interface HTTP 200, migration `f7b8c9d0e1f2`, flags falsas, token ausente e zero
runs/propostas. PostgreSQL/Redis foram preservados; OpenClaw/Mapalead permaneceram healthy.

O rollback é `idml-foundation:phase6-pre-gateway`, ID
`sha256:c6e0ef73c9e2ce9374381155460c4c04fd72246930295120c404cd880045d775`. O backup
`/opt/idml-platform/backups/20260827T204747Z` passou no restore com 21 tabelas e um artefato; o
snapshot anterior está em
`/opt/idml-platform/backups/source-phase6-pre-gateway-20260827T204747Z.tar.gz`.

## Incremento pós-gate — gateway OpenClaw dedicado e inerte

Em 2026-08-27 foi implantada uma segunda instância OpenClaw, exclusiva do IDML. A imagem 2026.6.11
está fixada pelo digest `sha256:3814fb1f62f9cfc5944de088c5817c68c88b5d721feebe36420b666a90a61ce7`;
o serviço tem volume e workspace próprios, token independente, rede Docker interna sem egress e
nenhuma porta publicada. Root filesystem é read-only, capabilities foram removidas e os limites são
384 MiB, 0,35 CPU e 120 PIDs.

O schema live foi validado sem warnings. Apenas `/v1/responses` está habilitado; Control UI e Chat
Completions estão desligados. Há um único agente `idml-evaluator`, modelo
`openai/gpt-5.4-mini`, nenhum fallback e listas vazias de ferramentas e Skills; plugins e canais
também estão desligados. Não existe provider key. API e worker só alcançam essa instância pela rede
dedicada e as duas flags de IA seguem falsas.

A observação prolongada detectou que o heartbeat padrão criava uma sessão e tentava resolver o
modelo. Não houve chamada de provider: egress estava bloqueado e não existia credencial. O heartbeat
foi desabilitado com `every: 0m` nos defaults e no agente, e `HEARTBEAT.md` ficou inerte. O volume,
criado apenas neste incremento, foi validado pelo label Compose, removido e recriado; o estado final
registra zero sessões e zero erros de modelo durante 105 segundos de observação; o banco da
aplicação registra zero runs/propostas. O runbook agora proíbe smoke em `/v1/responses` antes da
ativação controlada.

Localmente, 91 testes passaram com cobertura de 85,68%, além de Ruff, Mypy, sintaxe shell, schema
OpenClaw e Compose. Na VPS, OpenClaw dedicado, API, worker, PostgreSQL e Redis estão healthy;
migration `f7b8c9d0e1f2`; aplicação na imagem correta `phase6-gateway-v1`; OpenClaw compartilhado
com mesmo container, zero restarts e health saudável; Mapalead permaneceu em execução.

O backup `/opt/idml-platform/backups/20260827T212619Z` passou em checksums, restore isolado e
integridade SQLite, com 21 tabelas, um artefato e 13 arquivos de estado OpenClaw. O snapshot
pré-deploy é
`/opt/idml-platform/backups/source-phase6-pre-dedicated-openclaw-20260827T210633Z.tar.gz`. O Gate G6
continua bloqueado pela comprovação de ganho de qualidade e baseline humano; esta infraestrutura não
autoriza execução de agentes.

## Incremento pós-gate — staging controlado do provider

Em 2026-08-28 foi preparado o caminho opt-in do provider sem executar agentes. A configuração fixa
`openai/gpt-5.4-mini`, usava inicialmente proxy explícito e não grava chave no JSON. O Squid dedicado não publica
porta e permite somente `api.openai.com:443`; gateway e proxy compartilham uma rede interna, e
apenas o proxy possui rede com egress. API/worker continuam sem a chave e as duas flags permanecem
falsas.

A chave do OpenClaw existente foi reutilizada por autorização explícita e armazenada apenas como
`IDML_OPENAI_API_KEY` no `.env` modo 600. O risco de rotação compartilhada está documentado, sem
alteração do contêiner legado.

Os testes sem autenticação confirmaram túnel permitido, domínio externo negado com 403, saída direta
do gateway bloqueada, modelo único no catálogo e health estável. O banco e o estado OpenClaw
permaneceram com zero runs, propostas e sessões. O kill switch foi validado e o estado final está
desligado: proxy e redes removidos, credencial ausente de gateway/API/worker. O OpenClaw
compartilhado permaneceu healthy e com zero reinicializações. O backup
`/opt/idml-platform/backups/20260828T202601Z` passou restore isolado.

Este incremento encerra a preparação técnica de credencial/egress, mas não altera o Gate G6: a
primeira inferência depende de protocolo autorizado, e a aprovação continua exigindo ganho de
qualidade contra baseline humano.

## Incremento pós-gate — harness do benchmark controlado

Em 2026-08-31 foi implementado o harness fail-closed da primeira janela real, sem executar agentes.
O dataset privado v1.3 foi reconstruído com hashes conferidos e dez casos elegíveis. O plano escolhe
deterministicamente `esa-metadata-001` e `esa-references-001`, concorrência 1, uma tentativa por caso
e preflight total de 36.000 micro-USD sob o teto agregado de 50.000.

O runner exige flags falsas e uma confirmação transitória exata antes de `execute`. Input privado é
read-only; output fica modo 600; qualquer erro interrompe os casos restantes. A finalização sempre
aciona o kill switch, remove o provider e recria o estado do gateway dedicado. O teste negativo sem
confirmação parou antes do staging.

O dry-run local e o da VPS reproduziram o manifesto
`84feaa6d94bea033d6c53300c0ba742e4b51d5edd69a9736e376f45f6711956d`. Nenhum proxy ou rede de
provider foi criado, nenhuma chave entrou no gateway e permaneceram zero sessões, runs e propostas.
O reset do volume dedicado foi testado após corrigir a remoção segura do contêiner inicializador;
gateway dedicado e OpenClaw compartilhado terminaram healthy.

A imagem do runner é `idml-foundation:phase6-benchmark-v1`, ID
`sha256:7e559fa2a0cbdb527b75e5db3beb644e98bafaea83e7ac9e228f7a381cc6215f`. O backup
`/opt/idml-platform/backups/20260831T123026Z` passou no restore; o snapshot anterior é
`/opt/idml-platform/backups/source-phase6-pre-controlled-benchmark-20260831T123045Z.tar.gz`.
O backup final `/opt/idml-platform/backups/20260831T124753Z` também passou no restore isolado.

O estado de preparação foi posteriormente substituído pela execução controlada descrita abaixo.

## Incremento pós-gate — primeira janela controlada executada

Em 2026-09-01, após autorização explícita, a janela final
`esa-review-required-window-20260901` executou dois casos reais minimizados do artigo ESA. Um erro de
transporte foi diagnosticado no modo de proxy explícito do OpenClaw; a correção passou a usar o proxy
de ambiente do Node exclusivamente no gateway, mantendo o Squid allowlist e a saída direta bloqueada.

Os dois casos passaram em schema, evidência, paths autorizados, patch atômico quando exigido,
resistência à injeção e revisão obrigatória. Nenhuma ferramenta ou Skill foi exposta. O custo
contabilizado pelo catálogo `agent-pricing-1.1` foi 13.024 micro-USD, sob o teto de 50.000. A saída de
metadados foi exata. A saída de referências não melhorou a similaridade automática, embora tenha
preservado o conjunto de palavras; o alvo concatena duas representações e não constitui baseline
humano adjudicado.

O resultado bruto ficou privado em modo 600. O kill switch removeu credencial, proxy e redes, zerou
as sessões e deixou as flags falsas e zero `agent_runs`/`agent_proposals`. Gateway dedicado, API,
interface e OpenClaw compartilhado terminaram saudáveis, sem reinicialização do compartilhado. Os
backups `/opt/idml-platform/backups/20260901T134823Z` e
`/opt/idml-platform/backups/20260901T135404Z` passaram no restore isolado.

Essa janela resolve a pendência operacional e monetária do primeiro teste, mas não aprova o G6. A
qualidade por domínio continua inconclusiva até existir baseline e adjudicação humana autorizados.

## Incremento pós-gate — laboratório multiagente v1

Em 2026-09-01 foi implementado o laboratório técnico com proponente, crítico XML, crítico editorial
e adjudicador em sessões separadas. O alvo automático fica oculto dos quatro papéis; apenas saídas
estruturadas passam entre eles. Contratos fechados vinculam hashes de evidência, proposta e críticas,
e o juiz determinístico mantém precedência sobre o consenso.

A primeira configuração selecionou metadados e referências do corpus ESA, com até oito chamadas
sequenciais, tentativa única e preflight de 117.000 micro-USD sob o teto agregado de 150.000. O
mecanismo detecta consenso positivo sem ganho sobre o baseline e converte o resultado em abstenção.
Não há persistência na aplicação, aplicação de patch ou autorização de release; `needs_human=true`
é obrigatório.

A janela `multi-agent-first-window-v1` foi executada na VPS com custo de 32.824 micro-USD. O caso de
metadados chegou a consenso unânime e valor exato, permanecendo aceito apenas para futura revisão humana. Em
referências, o proponente produziu as duas representações atômicas de `RichText` com valores
inconsistentes; o juiz determinístico rejeitou antes dos críticos e do adjudicador. O defeito foi
transformado em fixture de regressão.

O relatório sanitizado confirmou zero ferramentas/Skills e não contém saídas brutas, prompts ou
alvo esperado. O pós-teste confirmou flags falsas, zero runs/propostas/sessões, credencial ausente do
gateway, proxy e redes transitórias ausentes, API/interface em HTTP 200 e ambos os OpenClaw healthy
com zero reinicializações. O backup `/opt/idml-platform/backups/20260901T152646Z` passou no restore
isolado. O G6-T permanece pendente pelos domínios e classes de caso ainda não executados.
