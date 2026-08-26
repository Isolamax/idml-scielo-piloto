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
