# Revisão do Gate G6 — IA assistiva e OpenClaw

Data: 2026-08-26. Estado do gate: **BLOQUEADO**.

## Resultado

A base técnica assistiva foi implementada e implantável em modo desativado: contratos
tenant-bound, schemas fechados por domínio, persistência append-only, orquestradores substituíveis,
timeout/retry/cancelamento, custo e concorrência limitados, prompts/modelos/configuração versionados
e propostas obrigatoriamente encaminhadas a humano. A autoridade de release continua inteiramente
determinística.

O gate não pode ser aprovado porque ainda não existe benchmark de um modelo real contra o baseline
humano por domínio. O registro usa deliberadamente `model_alias=unconfigured`; resultados do
`TestOrchestrator` provam os contratos, mas não são evidência de ganho de IA. O agente OpenClaw
atual também não atende a atestação dedicada de menor privilégio e, portanto, não foi alterado nem
conectado a conteúdo de artigos.

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
| IA melhora métrica sem elevar risco | PENDENTE | exige benchmark real/humano |
| patch exige schema, evidência e validação | PASSOU | serviço e testes de contrato |
| prompt injection não altera política | PASSOU | envelope não confiável + testes |
| custo máximo por artigo é respeitado | PASSOU | budget por run/Swarm |
| release continua determinístico | PASSOU | nenhuma ferramenta/rota de release para agentes |

## Decisão

A Fase 6 de fundação pode permanecer na VPS com `IDML_FEATURE_OPENCLAW=false` e
`IDML_FEATURE_AI_SWARM=false`. Isso não autoriza habilitar IA em artigos e não autoriza iniciar a
Fase 7. Para destravar G6 é necessário provisionar o agente dedicado/plugin restrito e executar um
corpus de avaliação separado, comparando cada domínio com revisão humana, custo e limites de risco
predefinidos.

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
`phase5` (`sha256:9ce77ba57e8270917f20e4691d02cac723b857af15c335f2e204ac672f1374b3`)
permanece para rollback. OpenClaw 2026.6.11 e os serviços Mapalead continuaram healthy e não foram
alterados. Nenhum corpus restrito foi enviado.
