# Plataforma IDML → XML SciELO

Monorepo da plataforma de conversão auditável de IDML para SciELO SPS/JATS.

Estado atual: **Fase 5 concluída — Gate G5 aprovado**. O pipeline gera JATS
1.3/SPS 1.10 e pacote determinístico sem IA, e agora possui revisão humana
auditável, interface mínima, MFA e dupla aprovação editorial. O Gate G4 continua
bloqueado por SPS/XPM, portanto `READY_FOR_SCIELO` segue corretamente negado.

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
- MFA TOTP, códigos de recuperação e reautenticação protegem ações sensíveis;
- revisão e aprovação editorial usam papéis distintos e histórico append-only;
- artefatos são imutáveis e endereçados por SHA-256;
- arquivos IDML são inspecionados antes de persistência;
- XML externo é processado sem entidades e sem rede;
- logs não devem conter tokens, senhas ou conteúdo integral de artigos.

Consulte [docs/PHASE_5_HUMAN_REVIEW.md](docs/PHASE_5_HUMAN_REVIEW.md), a
[revisão do Gate G5](docs/PHASE_5_GATE_REVIEW.md) e o
[plano por fases](PLANO_DESENVOLVIMENTO_POR_FASES.md).
