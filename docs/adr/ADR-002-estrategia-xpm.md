# ADR-002 — Estratégia de integração XPM

- Status: aceito com restrições
- Data: 2026-08-24

## Contexto

O XPM integra o pacote SciELO, mas a distribuição pública avaliada pressupõe Windows/Tk/Java, fixa dependências antigas e não executou headless Linux sem modificações.

## Decisão

Executar XPM em worker Windows dedicado, sem privilégios e desacoplado. A aplicação enviará pacote imutável e receberá relatório/evidências. Falha ou ausência de relatório nunca será sucesso.

## Consequências

Será necessário provisionar e proteger um worker Windows antes da Fase 4, confirmar automação/licenciamento e manter adapter substituível. O pipeline Linux continuará responsável por DTD, Packtools e regras próprias.
