# Fundação técnica e segurança — Fase 1

## Stack

- Python 3.12, FastAPI, Pydantic e SQLAlchemy 2;
- PostgreSQL 16 e Alembic;
- Redis 7 para sinalização de jobs; PostgreSQL é a fonte de verdade;
- storage content-addressed em volume filesystem;
- worker próprio de concorrência inicial 1;
- Docker Compose exclusivo `idml-development`.

Dependências Python estão travadas com hashes em `requirements.lock` e `requirements-dev.lock`. Versões principais resolvidas em 2026-08-24 incluem FastAPI 0.141.1, SQLAlchemy 2.0.52, Alembic 1.19.1, Redis client 6.4.0 e lxml 6.1.2.

## Ambientes

| Ambiente | Dados/secrets | Exposição | Finalidade |
|---|---|---|---|
| test | efêmeros/CI | nenhuma | unitários e segurança |
| development | próprios e gerados | API somente loopback | desenvolvimento na VPS |
| staging | separados e rotacionados | proxy/TLS futuro | homologação |
| production | secret manager/processo operacional | proxy/TLS | apenas após G7/G8 |

`IDML_ENVIRONMENT` valida defaults inseguros. OpenClaw e ClamAV são feature flags desligadas por padrão. Secrets reais são proibidos no repositório e CI.

## Persistência

Os conceitos são separados:

- versão semântica: `Resource.version` e, futuramente, versão do Canonical Model;
- execução: `Job`, único por empresa + idempotency key;
- tentativa: `attempt_count`, timestamps e transições;
- efeito: `JobEffect`, único por job + effect key;
- timeline: `JobEvent` append-only por sequência;
- auditoria: `AuditEvent` append-only na aplicação.

Transações do request fazem commit apenas após sucesso; exceções causam rollback. Concorrência de workers usa lock no carregamento do job e version/preconditions nas transições. PostgreSQL será o árbitro de unicidade.

## Artefatos

- SHA-256 define identidade do conteúdo;
- caminho é derivado de tenant + digest, nunca do nome enviado;
- gravação usa arquivo temporário, `fsync` e rename atômico;
- duplicata no mesmo tenant retorna o artefato existente;
- volume não é publicado e entra no backup;
- retenção inicial de desenvolvimento: 30 dias após o job, a ser automatizada na Fase 2; gold corpus segue política própria.

## Jobs

Estados:

```text
queued -> running -> succeeded
                  -> failed_retryable -> queued
                  -> failed_permanent
                  -> cancelled
queued -> quarantined | cancelled
```

- máximo inicial de 3 tentativas;
- backoff inicial 30 s, futuro exponencial com jitter;
- cancelamento é persistido e verificado entre etapas;
- replay cria nova execução/idempotency key e referencia a anterior;
- restart não perde job: Redis só sinaliza e o banco mantém o estado;
- efeito externo exige `JobEffect` antes/depois conforme contrato e chave única.

## Ingestão segura

Limites padrão: upload 100 MiB, 5.000 entradas e 500 MiB descompactados, razão máxima 100:1. São bloqueados traversal, caminhos absolutos, duplicatas, symlinks/special entries, criptografia, arquivos aninhados e IDML sem `mimetype`/`designmap.xml`.

XML externo rejeita DOCTYPE/ENTITY e usa lxml com `resolve_entities=False`, `load_dtd=False`, `no_network=True` e `huge_tree=False`. ClamAV possui adapter por feature flag; na VPS pequena fica desligado até haver serviço dedicado ou scanner externo. Mesmo sem ele, policy scanning é obrigatório e malware conhecido não pode ser liberado.

## Observabilidade

- JSON logs com timestamp, nível, logger, correlation ID, tenant, job e evento;
- sanitização de nomes sensíveis e ausência de bodies/tokens;
- `/health/live`, `/health/ready` e `/metrics`;
- métricas HTTP, banco/Redis no readiness e limites Docker;
- timeline de job e auditoria permitem reconstrução;
- logs Docker rotacionam em 3 × 10 MiB por container.

Alertas mínimos: readiness falho 5 min, container reiniciando, fila crescente, job preso, disco >85%, memória/swap em pressão, backup falho/antigo e evento de segurança repetido.

## Definition of Done da fundação

- lint Ruff e formatação passam;
- mypy strict passa;
- testes e cobertura mínima de 80% passam;
- migration upgrade/downgrade/upgrade reproduzível;
- stack Compose saudável;
- backup e restore testados;
- isolamento de tenant, ZIP malicioso, XXE e idempotência testados;
- apenas API loopback; banco e Redis sem portas publicadas.

