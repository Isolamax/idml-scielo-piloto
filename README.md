# Plataforma IDML → XML SciELO

Monorepo da plataforma de conversão auditável de IDML para SciELO SPS/JATS.

Estado atual: **Fase 4 implementada — Gate G4 bloqueado**. O pipeline gera JATS
1.3/SPS 1.10 e pacote determinístico sem IA; SPS/editorial e XPM ainda impedem
`READY_FOR_SCIELO`. A Fase 5 não está autorizada.

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
profiles/               perfis de periódico e mapeamentos de estilo versionados
vendor/                 DTD JATS oficial fixada para validação offline
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

Conversão local determinística:

```bash
idml-admin pipeline-convert --input artigo.idml --output artigo.xml \
  --report validation.json --raw raw.json --canonical canonical.json
```

O XML gold não é parâmetro do conversor. Avaliações restritas usam somente gates
locais; binários reais não entram em Git, CI, imagem ou VPS.

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
- XML externo é processado sem entidades e sem rede;
- logs não devem conter tokens, senhas ou conteúdo integral de artigos.

Consulte [docs/PHASE_1_FOUNDATION.md](docs/PHASE_1_FOUNDATION.md) e o [plano por fases](PLANO_DESENVOLVIMENTO_POR_FASES.md).
