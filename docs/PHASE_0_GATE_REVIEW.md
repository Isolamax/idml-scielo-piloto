# Gate G0 — Descoberta e viabilidade

## Resultado

```text
GATE: G0
STATUS: APPROVED_WITH_CONSTRAINTS
DECISION: GO_WITH_CONSTRAINTS
APPROVED_AT: 2026-08-24
NEXT_PHASE: FASE 1 — aguardando autorização explícita
```

## Checklist de saída

- [x] Reading order possui estratégia tecnicamente plausível.
  - Evidência: [IDML_MODEL_ANALYSIS.md](IDML_MODEL_ANALYSIS.md), threads + página/coluna/geometria + estilos + objetos ancorados.
- [x] Versão SPS/JATS inicial foi definida.
  - Evidência: [SCIELO_REQUIREMENTS.md](SCIELO_REQUIREMENTS.md), SPS 1.10/JATS Publishing 1.3.
- [x] Packtools foi provado.
  - Evidência: [PACKTOOLS_SPIKE.md](PACKTOOLS_SPIKE.md), execução Linux e 1.020 resultados estruturados.
- [x] XPM possui caminho de integração decidido.
  - Evidência: [XPM_FEASIBILITY.md](XPM_FEASIBILITY.md), worker Windows dedicado.
- [x] OpenClaw foi auditado sem alteração.
  - Evidência: [OPENCLAW_SWARM_DESIGN.md](OPENCLAW_SWARM_DESIGN.md).
- [x] Corpus piloto foi selecionado.
  - Evidência: conjunto ESA com IDML/PDF/XML/assets/XPM e corpus RBEdu complementar.
- [x] Infraestrutura para desenvolvimento foi aprovada.
  - Evidência: [ENVIRONMENT_BASELINE.md](ENVIRONMENT_BASELINE.md), VPS atual com isolamento e limites.
- [x] Decisão formal registrada.
  - Evidência: [ARCHITECTURE_REVIEW.md](ARCHITECTURE_REVIEW.md), `GO_WITH_CONSTRAINTS`.

## Condições transportadas para a Fase 1

- nenhuma alteração em produção ou no OpenClaw sem tarefa específica;
- novo Compose e recursos totalmente separados;
- concorrência inicial dos workers igual a 1;
- limites de CPU/RAM/log/disco e monitoramento antes dos jobs pesados;
- Packtools em imagem pinada e sem instalação no host;
- autenticação, empresa, usuário, RBAC, auditoria e isolamento de tenant desde a primeira migration;
- XPM planejado como worker Windows, mas sua integração funcional pertence à Fase 4;
- nenhuma funcionalidade de IA até existir baseline determinístico.

## Fora do escopo deste encerramento

Não foram criados repositório de aplicação, banco, serviços, endpoints, migrations, telas ou pipeline. A Fase 0 produziu apenas pesquisa, spikes descartáveis, auditoria e documentação de decisões.
