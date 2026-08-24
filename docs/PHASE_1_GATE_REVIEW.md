# Revisão do Gate G1 — Fundação técnica e segurança

- Data: 2026-08-24
- Ambiente: desenvolvimento isolado na VPS atual
- Decisão: `APPROVED`
- Produção: não autorizada

## Evidências automatizadas

- Ruff check e format: aprovados;
- mypy strict: aprovado em 26 módulos;
- pytest: 26 testes aprovados;
- cobertura: 85,10%, acima do mínimo de 80%;
- migration Alembic reproduzida em upgrade/downgrade/upgrade e aplicada no
  PostgreSQL com head `055fc21c9963`;
- dependências Python instaladas por lockfiles com hashes.

## Evidências na VPS

| Controle | Evidência | Resultado |
|---|---|---|
| Stack | API, worker, PostgreSQL e Redis healthy | Aprovado |
| Exposição | API em `127.0.0.1:18080`; PostgreSQL/Redis sem porta no host | Aprovado |
| Multiempresa | usuário da empresa A recebeu 404 para recurso da empresa B | Aprovado |
| Ingestão hostil | IDML com `../escape.txt` recebeu 422 `path_traversal` | Aprovado |
| Storage | IDML válido persistido por SHA-256 com container não-root | Aprovado |
| Idempotência | dois POSTs retornaram o mesmo job | Aprovado |
| Efeito único | job terminou `succeeded` com exatamente um `JobEffect` | Aprovado |
| Auditoria | timeline `queued,running,succeeded` e login correlacionado | Aprovado |
| Backup | dump PostgreSQL + volume de artefatos, SHA-256 e modo 600 | Aprovado |
| Restore | checksums, 13 tabelas e artefato restaurados em destinos temporários | Aprovado |
| Agenda | timer systemd diário ativo, persistente e com atraso aleatório | Aprovado |

Backup de prova: `/opt/idml-platform/backups/20260824T175151Z`. A imagem validada
possui ID `sha256:0f43e8bc896116f5deb5c280640858ddd5b7b16e054f8ab8bcecdd2bd8ba4999`.

No snapshot do gate, os limites e consumos foram:

- API: 67,84 MiB / 256 MiB;
- worker: 50,46 MiB / 256 MiB;
- PostgreSQL: 59,3 MiB / 384 MiB;
- Redis: 6,85 MiB / 96 MiB;
- disco: 21 GB livres;
- memória disponível reportada: 1,4 GiB.

## Isolamento operacional

- projeto em `/opt/idml-platform` e Compose `idml-development`;
- networks e volumes possuem prefixo exclusivo;
- `.env` é `root:root` modo 600 e backups são `root:root` modo 700/600;
- `idmladmin` é usuário de acesso não-root, sem Docker e sem sudo;
- nenhum site Nginx ou domínio público foi criado;
- OpenClaw e Mapalead não foram modificados.

## Restrições transportadas

- ambiente permanece exclusivamente de desenvolvimento;
- ClamAV continua desligado nesta VPS pequena; o adapter e a política de
  quarentena estão preparados, e sua ativação requer scanner dedicado/externo;
- MFA, recuperação e convites têm modelo e política definidos, mas a interface e
  os fluxos completos pertencem à Fase 5, antes de produção;
- proteção de branch no servidor deverá ser habilitada quando um remoto for
  escolhido; o CI, a política e o bloqueio local já estão versionados;
- a capacidade continuará monitorada; upgrade de hardware será feito apenas se
  as medições demonstrarem necessidade.

O Gate G1 está aprovado. A Fase 2 permanece não autorizada até solicitação
explícita do responsável.
