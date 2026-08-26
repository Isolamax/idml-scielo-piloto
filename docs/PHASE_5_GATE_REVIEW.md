# Revisão do Gate G5 — Revisão humana e interface mínima

- Data: 2026-08-26
- Ambiente: desenvolvimento local e runtime de desenvolvimento na VPS
- Decisão local: `APPROVED`
- Gate G4: permanece `BLOCKED`
- Produção: não autorizada

## Checklist G5

| Critério | Evidência | Estado |
|---|---|---|
| Corrigir sem editar XML | API aplica patch no modelo e reconstrói JATS | Aprovado |
| Bloquear usuário sem permissão | release manager recebe 403 em decisão de revisão | Aprovado |
| Isolamento entre empresas | identificador de outro tenant retorna 404 | Aprovado |
| Controle de concorrência | versão obsoleta retorna 409 | Aprovado |
| Nova versão e revalidação | snapshot filho + ReviewBuild/validação | Aprovado |
| Histórico íntegro | snapshots, decisões e builds append-only | Aprovado |
| Reconstrução pelo auditor | ator, empresa, patch/hash, diff, XML e auditoria | Aprovado |
| MFA em ações sensíveis | TOTP/recovery/replay e sessão MFA testados | Aprovado |
| Dupla aprovação | solicitante bloqueado e dois aprovadores distintos | Aprovado |
| Separação do gate técnico | estado `editorially_approved`, nunca READY | Aprovado |

## Verificações locais

- `ruff check .`: aprovado;
- `mypy src`: aprovado;
- `pytest`: 57 testes aprovados;
- cobertura: 85,26%, acima do mínimo de 80%;
- Alembic: upgrade até `c4e5f6a7b8c9`, downgrade para `8af62bb716cf` e novo
  upgrade aprovados em banco efêmero.

## Riscos residuais

- TOTP é o único segundo fator nesta fase; WebAuthn pode ser acrescentado;
- rate limiting distribuído deve preceder exposição pública da interface;
- a UI é deliberadamente mínima e não substitui testes de acessibilidade/UX;
- a aprovação editorial não resolve os erros SPS nem a ausência do XPM que
  mantêm o Gate G4 bloqueado.

## Condição da próxima fase

O Gate G5 autoriza iniciar a Fase 6 de IA assistiva. Isso não autoriza produção,
nem habilita OpenClaw, nem amplia a autoridade de IA sobre release.
