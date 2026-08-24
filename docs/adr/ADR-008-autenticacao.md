# ADR-008 — Autenticação local e evolução OIDC

- Status: aceito
- Data: 2026-08-24

## Decisão

Iniciar com Argon2 e sessões opacas revogáveis. Manter autenticação atrás de adapter para OIDC futuro. Autorização e tenants permanecem internos.

## Consequências

Recuperação, convite, MFA e reautenticação seguem tokens de uso único e auditoria. Produção exige MFA para perfis sensíveis antes do Gate G5.

