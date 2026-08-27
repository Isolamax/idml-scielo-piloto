# Revisão do Gate G6 — IA assistiva e OpenClaw

Data: 2026-08-26. Estado do gate: **BLOQUEADO**.

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

## Decisão

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
