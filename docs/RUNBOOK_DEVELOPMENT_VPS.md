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
`/opt/idml-platform`. Smoke tests na VPS usam apenas o IDML sintético dos testes. Benchmarks
explicitamente autorizados podem usar somente fragmentos minimizados em
`benchmarks/private`, modo 600; respostas brutas permanecem privadas e apenas métricas
sanitizadas podem ser versionadas.
Rollback da aplicação permanece pela tag anterior (`phase3`).

## Fase 5 — identidade e revisão humana

`IDML_MFA_ENCRYPTION_KEY` é obrigatório no Compose, deve conter segredo aleatório
independente do session pepper e permanecer modo 600 em `.env`. Não imprimir a
chave em verificações; validar somente presença/comprimento. A rotação exige
procedimento próprio porque os segredos TOTP persistidos dependem dela.

A UI permanece acessível somente pelo bind loopback da API. Antes de exposição
pública, adicionar proxy TLS e rate limiting distribuído. A aprovação de duas
pessoas resulta em `editorially_approved` e não substitui a Release Policy nem
concede `READY_FOR_SCIELO`.

Na atualização da Fase 5, preservar a tag `phase4`, executar backup/restore test,
aplicar a migration `c4e5f6a7b8c9` e recriar somente `api` e `worker`. A migration
é aditiva e a imagem anterior pode ser usada para rollback da aplicação enquanto
se investiga um incidente.

## Fase 6 — IA assistiva desativada

A fundação da Fase 6 deve operar com `IDML_FEATURE_OPENCLAW=false` e
`IDML_FEATURE_AI_SWARM=false`. Não conectar o agente pessoal existente ao conteúdo de artigos. O
agente dedicado `idml-evaluator` é exclusivo para avaliação offline, sem bindings, Skills ou
ferramentas efetivas. Uma ativação futura exige plugin de ferramentas tenant-bound, atestação
completa, custo observável e benchmark real aprovado no Gate G6.

O custo segue `docs/AGENT_COST_POLICY.md`. Se `/v1/ai/capabilities` retornar `priced_models=[]` e o
gateway não fornecer custo por chamada, manter as duas flags falsas. Nunca preencher o catálogo
por aproximação de família ou alias: uma resposta sem custo deve terminar em `COST_UNAVAILABLE`.

Em deploy, validar dentro da imagem que `load_registry()` encontra seis perfis e que todos os
prompts carregam. Validar também `load_pricing_catalog()`, executar backup/restore, aplicar a
migration `e6a7b8c9d0e1` e recriar somente API
e worker. Preservar `phase5` como rollback da aplicação; a migration é aditiva e pode permanecer
enquanto um incidente é investigado. Confirmar zero `agent_runs`/`agent_proposals` enquanto as
features estiverem desabilitadas.
