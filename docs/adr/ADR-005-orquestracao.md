# ADR-005 — Orquestração substituível

- Status: aceito
- Data: 2026-08-24

## Contexto

O OpenClaw instalado possui agentes, ferramentas, hooks e plugins, porém não foi confirmada uma primitiva estável chamada Swarm. O pipeline não pode depender de uma API experimental nem de sessões de agente.

## Decisão

Definir uma porta de orquestração própria. `SequentialOrchestrator` será o padrão; OpenClaw será adapter opcional por feature flag; modo sem IA permanecerá funcional.

## Consequências

Agentes só propõem patches tipados e nunca aprovam release. Estado fica no banco da aplicação. Cada execução terá schema, allowlist de ferramentas, timeout, budget, idempotency key e auditoria.
