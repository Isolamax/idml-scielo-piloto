# ADR-007 — Fila e execução de jobs

- Status: aceito
- Data: 2026-08-24

## Decisão

PostgreSQL é a fonte de verdade para estado/timeline/idempotência; Redis apenas sinaliza IDs. O commit durável ocorre antes do sinal. O worker começa com concorrência 1, consulta jobs `queued` como recuperação quando o sinal se perde e efeitos possuem chave única.

## Consequências

Restart, corrida de commit ou perda do Redis não perdem estado nem deixam o job permanentemente preso. Escala horizontal usa lock PostgreSQL no processamento e exigirá métricas adicionais de fila antes de aumentar a concorrência.
