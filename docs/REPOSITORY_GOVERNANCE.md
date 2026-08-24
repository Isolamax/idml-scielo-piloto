# Governança do repositório

## Fluxo

- `main` representa a base integrada e não recebe push direto;
- mudanças usam branches curtas `codex/<descricao>` ou `<tipo>/<descricao>`;
- toda integração exige pull request, CI verde e ao menos uma revisão;
- force-push e exclusão de `main` são proibidos;
- migrations, segurança e ADRs devem ser revisados explicitamente.

O hook versionado em `.githooks/pre-push` aplica o bloqueio local. Este clone usa
`core.hooksPath=.githooks`. Quando um remoto GitHub/GitLab for conectado, a mesma
política deverá ser habilitada no servidor com os checks `quality` obrigatórios,
uma aprovação e resolução das conversas. Não há remoto configurado nesta fase,
portanto nenhuma credencial ou repositório externo foi criado por suposição.

## Critérios do pull request

- Ruff check e format;
- mypy strict;
- pytest com cobertura mínima de 80%;
- migration reproduzível quando o schema mudar;
- busca de credenciais e chaves;
- documentação, riscos e ADR coerentes com o comportamento.

O CI usa somente SQLite efêmero, Redis local de teste e segredo sintético. Dados e
credenciais da VPS não entram no Git nem no executor de CI.
