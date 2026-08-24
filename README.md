# Plataforma IDML → XML SciELO

Monorepo da plataforma de conversão auditável de IDML para SciELO SPS/JATS.

Estado atual: **Fase 2 concluída — Gate G2 aprovado**. A Fase 3 aguarda autorização.

## Estrutura

```text
src/idml_foundation/   API, domínio da fundação, segurança e worker
corpus/                manifestos e expectativas; binários privados fora do Git
schemas/               contratos JSON Schema versionados
tests/                 testes unitários, integração e segurança
migrations/            migrations Alembic
deploy/                 imagens, Compose e configuração operacional
ops/                    backup, restore e verificações
docs/                   arquitetura, ADRs e runbooks
```

## Desenvolvimento

Pré-requisitos: Python 3.12 e Docker Compose.

```bash
python -m venv .venv
. .venv/bin/activate
pip install --require-hashes -r requirements-dev.lock
pip install --no-deps -e .
pytest
ruff check .
ruff format --check .
mypy src
```

Para o stack completo:

```bash
cp .env.example .env
docker compose -f deploy/docker-compose.dev.yml up --build -d
```

Use apenas credenciais locais geradas para desenvolvimento. Nunca copie secrets de produção para `.env`.

## Segurança

- isolamento por organização é obrigatório no backend;
- autorização possui negação por padrão;
- sessões são opacas e revogáveis;
- artefatos são imutáveis e endereçados por SHA-256;
- arquivos IDML são inspecionados antes de persistência;
- XML externo será processado sem entidades e sem rede;
- logs não devem conter tokens, senhas ou conteúdo integral de artigos.

Consulte [docs/PHASE_1_FOUNDATION.md](docs/PHASE_1_FOUNDATION.md) e o [plano por fases](PLANO_DESENVOLVIMENTO_POR_FASES.md).
