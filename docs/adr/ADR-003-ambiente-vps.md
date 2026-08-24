# ADR-003 — Ambiente inicial na VPS atual

- Status: aceito com restrições
- Data: 2026-08-24

## Contexto

A VPS HostGator possui 2 vCPU, 3,8 GiB RAM e 21 GiB livres, e já executa Mapalead, OpenClaw, bancos e workers. O usuário decidiu iniciar sem upgrade preventivo.

## Decisão

Usar a VPS atual para desenvolvimento inicial e piloto, em projeto Compose, rede, volumes, banco, fila e credenciais exclusivos, com limites e concorrência inicial 1. Upgrade somente por métricas.

## Consequências

Disco, swap, CPU, latência e reinícios serão monitorados. Não haverá `prune` global nem compartilhamento de recursos de aplicação. A Fase 1 deverá criar a fundação isolada antes de qualquer pipeline.
