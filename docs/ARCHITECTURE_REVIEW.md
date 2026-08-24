# Revisão de arquitetura — encerramento da Fase 0

## Decisão executiva

```text
DECISION: GO_WITH_CONSTRAINTS
DATE: 2026-08-24
PHASE_0: COMPLETE
PHASE_1: NOT_STARTED
```

É tecnicamente viável iniciar a plataforma na VPS atual sem upgrade preventivo. O desenvolvimento deverá ser isolado dos serviços existentes, começar com concorrência baixa e medir recursos. A arquitetura deve manter parser, modelo, builder, validação e release determinísticos; IA/OpenClaw será opcional e tardia.

## Evidências do Gate G0

| Tema | Evidência | Conclusão |
|---|---|---|
| Infraestrutura | [ENVIRONMENT_BASELINE.md](ENVIRONMENT_BASELINE.md) | VPS utilizável com limites; disco, swap e firewall exigem controle |
| SciELO | [SCIELO_REQUIREMENTS.md](SCIELO_REQUIREMENTS.md) | alvo SPS 1.10/JATS 1.3 definido |
| Packtools | [PACKTOOLS_SPIKE.md](PACKTOOLS_SPIKE.md) | execução Linux e saída estruturada comprovadas |
| XPM | [XPM_FEASIBILITY.md](XPM_FEASIBILITY.md) | worker Windows dedicado; integração desacoplada |
| IDML | [IDML_MODEL_ANALYSIS.md](IDML_MODEL_ANALYSIS.md) | corpus gold e estratégia de reading order definidos |
| OpenClaw | [OPENCLAW_SWARM_DESIGN.md](OPENCLAW_SWARM_DESIGN.md) | auditado sem alteração; adapter opcional e fallback sequencial |

## Arquitetura aprovada

Fluxo principal:

```text
Upload seguro
  -> Artifact Store imutável
  -> Parser IDML determinístico
  -> Canonical Article Model versionado
  -> regras/mapeamentos do periódico
  -> ReviewItems e patches tipados
  -> builder SPS 1.10/JATS 1.3
  -> DTD + Packtools + regras próprias
  -> Package Builder
  -> XPM Windows
  -> Release Policy determinística
  -> pacote liberado ou revisão humana
```

OpenClaw/IA atua apenas lateralmente sobre ReviewItems e nunca substitui o fluxo ou seus gates.

## Controle de acesso e isolamento

O plano incorpora empresa, usuário e autorização como parte estrutural, não como tela adicional:

- `Company/Tenant` é a raiz de isolamento;
- `User` possui identidade, estado, MFA/reautenticação quando aplicável e vínculo a empresas;
- memberships associam papel e escopo;
- RBAC mínimo: administrador da plataforma, administrador da empresa, operador, revisor e responsável por release;
- queries, jobs, storage keys, filas e eventos carregam `tenant_id` validado no backend;
- revisão e release são permissões separadas;
- ações sensíveis geram auditoria append-only com usuário, empresa, objeto, versão e justificativa;
- OpenClaw e workers nunca decidem autorização;
- testes negativos entre empresas são obrigatórios antes do Gate G5.

A decisão entre autenticação local segura e OIDC será tomada na Fase 1, sem enfraquecer o modelo de tenant/RBAC.

## Restrições não negociáveis

1. nenhum dado ausente será inventado;
2. XML final não será editado livremente por IA;
3. ZIP será lido com limites e proteção contra traversal/zip bomb;
4. parsers XML operarão sem rede e sem entidades externas;
5. perfil SPS e validadores serão pinados por job;
6. jobs e patches serão idempotentes e auditáveis;
7. release dependerá de policy versionada, não de resposta textual;
8. dados e credenciais não serão compartilhados entre o novo projeto, Mapalead e OpenClaw;
9. a VPS não sofrerá upgrade preventivo; medições abrirão essa decisão;
10. não haverá deploy de produção durante as fases de fundação.

## Matriz inicial de riscos

Escala: probabilidade (P) e impacto (I) de 1 a 5; exposição = P × I.

| ID | Risco | P | I | Exposição | Tratamento inicial | Dono/fase |
|---|---|---:|---:|---:|---|---|
| R-01 | reading order incorreto | 4 | 5 | 20 | threads + geometria + estilos + corpus gold + revisão visual | Engenharia, F2–F3 |
| R-02 | XPM não automatizável em Linux | 5 | 4 | 20 | worker Windows desacoplado; confirmação de automação/licença | Plataforma, F1/F4 |
| R-03 | mudança SPS/validadores defasados | 4 | 5 | 20 | SpsProfile pinado, exceções específicas e regressão | XML, F1–F8 |
| R-04 | VPS insuficiente | 3 | 4 | 12 | limites, concorrência 1, monitoramento e upgrade sob demanda | Infra, F1–F8 |
| R-05 | impacto em Mapalead/OpenClaw | 3 | 5 | 15 | Compose/network/volumes exclusivos e reserva de recursos | Infra, F1 |
| R-06 | prompt injection por artigo | 4 | 4 | 16 | conteúdo não confiável, tools allowlisted e schemas | IA/Sec, F6 |
| R-07 | vazamento entre empresas | 3 | 5 | 15 | tenant no backend/storage/fila; testes negativos | Backend/Sec, F1/F5 |
| R-08 | modelo canônico insuficiente | 4 | 4 | 16 | corpus antes do congelamento e modelo versionado | Domínio, F2 |
| R-09 | confiança de IA mal calibrada | 4 | 4 | 16 | dataset, evidência, limiares e revisão humana | IA, F6–F7 |
| R-10 | custo/latência excessivos | 3 | 3 | 9 | routing, orçamento, cache seguro e modo sem IA | IA/Produto, F6–F8 |
| R-11 | job não retomável | 3 | 4 | 12 | estados, idempotency keys, retry e replay | Backend, F1/F3 |
| R-12 | perda de dados/histórico | 2 | 5 | 10 | imutabilidade, backup e restore próprios | Infra, F1 |
| R-13 | ZIP/IDML malicioso | 4 | 5 | 20 | inspeção sem extração, limites e sandbox | Sec, F1/F3 |
| R-14 | licenciamento/automação XPM incertos | 3 | 4 | 12 | confirmação formal antes da homologação | Produto, F4/F7 |
| R-15 | limpeza indevida do Docker compartilhado | 2 | 5 | 10 | proibir prune global; manutenção por projeto | Infra, F1–F8 |

## Débitos aceitos para entrada na Fase 1

Estes itens não invalidam a viabilidade, mas viram critérios da fundação:

- criar usuário administrativo não-root e política de acesso à VPS;
- definir regra de firewall sem interromper os serviços atuais;
- controlar ocupação de disco e retenção;
- criar Compose, secrets, banco, fila e storage exclusivos;
- escolher autenticação local/OIDC e produzir threat model;
- construir imagem pinada do Packtools;
- preparar plano do worker Windows, sem integrá-lo ainda.

## Decisão de infraestrutura

Usar a VPS como está hoje para Fases iniciais e piloto. Upgrade será proposto somente quando telemetria mostrar pressão de memória/swap, CPU, disco, latência, reinícios ou demanda de concorrência. O novo serviço começa pequeno e isolado.
