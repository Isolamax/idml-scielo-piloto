# ADR-009 — RBAC e isolamento multiempresa

- Status: aceito
- Data: 2026-08-24

## Decisão

`Organization` é raiz de isolamento. Membership define papel por empresa; permissões são allowlist com negação padrão. Toda query, job, storage key e auditoria carrega tenant validado no backend.

## Consequências

Usuário pode pertencer a várias empresas sem compartilhar recursos. Testes negativos cross-tenant são obrigatórios. Banco poderá receber RLS como defesa adicional antes de produção.

