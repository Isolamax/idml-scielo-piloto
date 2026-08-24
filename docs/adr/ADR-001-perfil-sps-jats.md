# ADR-001 — Perfil SPS/JATS inicial

- Status: aceito
- Data: 2026-08-24

## Contexto

O corpus aprovado usa SPS 1.9/JATS 1.1, mas a comunicação SciELO vigente exige SPS 1.10. A versão SPS 1.10 suporta JATS mais recente e o projeto precisa evitar um alvo já legado.

## Decisão

Emitir inicialmente `specific-use="sps-1.10"` com JATS Journal Publishing DTD 1.3. Perfil, DTD, builder, validadores e exceções serão pinados e versionados por job.

## Consequências

O XML gold será referência semântica, não modelo copiável. Validadores ainda defasados exigirão exceções específicas e auditáveis. Upgrade para SPS/JATS futuro será novo perfil, nunca alteração silenciosa.
