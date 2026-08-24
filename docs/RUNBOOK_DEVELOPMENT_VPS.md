# Runbook — ambiente de desenvolvimento na VPS

## Localização e isolamento

- diretório: `/opt/idml-platform`;
- Compose project: `idml-development`;
- rede interna: `idml_development_internal`;
- volumes: `idml_development_postgres`, `idml_development_redis`, `idml_development_artifacts`;
- API: `127.0.0.1:18080`; não publicar externamente.

## Subir/atualizar

```bash
cd /opt/idml-platform
docker compose --env-file .env -f deploy/docker-compose.dev.yml config --quiet
docker compose --env-file .env -f deploy/docker-compose.dev.yml build
docker compose --env-file .env -f deploy/docker-compose.dev.yml up -d
ops/verify-stack.sh
```

O serviço `migrate` precisa terminar com sucesso antes de API/worker. Não use `docker system prune`.
Em atualização rotineira, não use `--force-recreate` sobre toda a stack: recrie
somente `migrate`, `api`, `worker` e inicializadores necessários. PostgreSQL e
Redis só devem ser recriados em manutenção planejada, preservando os volumes.

## Verificar

```bash
docker compose --env-file .env -f deploy/docker-compose.dev.yml ps
curl --fail http://127.0.0.1:18080/health/ready
docker compose --env-file .env -f deploy/docker-compose.dev.yml logs --tail=100 api worker
```

## Backup e restore

```bash
backup_dir=$(ops/backup.sh)
ops/restore-test.sh "$backup_dir"
```

Os scripts carregam `/opt/idml-platform/.env` sem imprimir seu conteúdo. Backups
ficam fora dos volumes Docker, em `/opt/idml-platform/backups`, modo 600 e com
SHA-256. Restore de produção exige janela, aprovação e destino novo; nunca
sobrescrever banco ativo durante teste.

O timer `idml-development-backup.timer` executa o backup diariamente às 04:40 no
fuso `America/Sao_Paulo`, com atraso aleatório de até 10 minutos. Verifique com:

```bash
systemctl status idml-development-backup.timer
systemctl status idml-development-backup.service
```

## Incidentes

1. registrar horário e correlation/job ID sem copiar secrets;
2. verificar health, `docker stats --no-stream`, disco e eventos OOM;
3. pausar entrada de novos jobs antes de reiniciar worker;
4. preservar banco, volumes e logs;
5. rollback de imagem por tag anterior; migrations destrutivas são proibidas sem plano expand/contract;
6. testar restore em banco alternativo.

## Fase 4 — validadores externos

O runtime principal contém apenas validação offline e contratos da Fase 4. O
Packtools/SPSValidator roda em ambiente isolado e nunca recebe corpus restrito na
VPS. O XPM deve executar em Windows Worker; ausência do worker produz
`VALIDATION_UNAVAILABLE`.

Não copie IDML, PDF, XML real, assets, relatórios XPM ou ZIP candidato para
`/opt/idml-platform`. Smoke tests na VPS usam apenas o IDML sintético dos testes.
Rollback da aplicação permanece pela tag anterior (`phase3`).
