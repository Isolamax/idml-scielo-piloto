# ADR-007 — Fila e execução de jobs

- Status: aceito
- Data: 2026-08-24

## Decisão

PostgreSQL é a fonte de verdade para estado/timeline/idempotência; Redis apenas sinaliza IDs. Worker começa com concorrência 1 e efeitos possuem chave única.

## Consequências

Restart ou perda do Redis não perde estado. Um reconciliador futuro reenfileira jobs `queued`. Escala horizontal exigirá locks PostgreSQL e métricas de fila.

