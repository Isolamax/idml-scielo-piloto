# ADR-006 — Storage de artefatos

- Status: aceito
- Data: 2026-08-24

## Decisão

Usar volume filesystem content-addressed por SHA-256 e tenant na VPS inicial. Escrita atômica e metadados no PostgreSQL. Definir uma porta para migração futura a S3 compatível.

## Consequências

Menor consumo que MinIO na VPS atual. Backup precisa cobrir volume e banco de forma coordenada. O volume não é público e nomes enviados não determinam paths.

