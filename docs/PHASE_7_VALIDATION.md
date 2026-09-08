# Fase 7 — Homologação automatizada e piloto simulado

Data inicial: 2026-09-04. Estado: **EM EXECUÇÃO — V-01 E V-02 CONCLUÍDOS**.

## Estado das famílias V-01 a V-11

| Família | Estado | Evidência atual |
|---|---|---|
| V-01 Proveniência e integridade | PASSOU | catálogo e gate reproduzível |
| V-02 Segurança da ingestão | PASSOU | matriz negativa, regressão e VPS |
| V-03 Leitura e fidelidade IDML | PENDENTE | próxima execução |
| V-04 Canonical Article Model | PENDENTE | — |
| V-05 Construção JATS/SPS | PENDENTE | — |
| V-06 Validadores formais | PENDENTE | — |
| V-07 Fidelidade comparativa | PENDENTE | — |
| V-08 OpenClaw assistivo | PENDENTE | evidências da Fase 6 serão reexecutadas no gate consolidado |
| V-09 Segurança e multiempresa | PENDENTE | — |
| V-10 Fluxo ponta a ponta | PENDENTE | — |
| V-11 Robustez e mutações | PENDENTE | — |

## V-01 — Proveniência e integridade do corpus

O gate `ops/gate_phase7_v01.py` consolida os seis manifestos e falha fechado em caso de:

- ID de corpus ou caminho lógico duplicado;
- mesmo SHA-256 reutilizado entre corpus ou splits;
- classificação de artefato mais fraca que a do corpus;
- redistribuição ou exclusão insegura de conteúdo restrito;
- arquivo restrito idêntico presente no conjunto versionável;
- nome, ID ou hash do holdout presente em prompts, testes ou material de benchmark executável;
- caminho de source root inseguro;
- arquivo privado ausente, truncado, substituído, em symlink ou com hash divergente.

A execução local verificou 21/21 artefatos nos roots privados autorizados sem emitir conteúdo. O
catálogo contém seis manifestos, um holdout e zero duplicata, contaminação entre splits ou falha de
classificação. A varredura local calculou hash de 404 arquivos versionados/versionáveis e inspecionou
88 arquivos textuais de execução; nenhum binário restrito ou token do holdout foi encontrado.

O fingerprint canônico do catálogo é
`6869ea39c818a9036f8f949a79a616f8f407195464b18bdfcd98e3b11e21207d`. A mesma verificação de
metadados foi reproduzida na VPS em container read-only e sem rede, com fingerprint idêntico. A CI
executará o gate a cada mudança. Os binários privados não foram copiados para a VPS nem para a CI.

A suíte completa terminou com 199 testes, cobertura de 84,89%, Ruff e mypy strict aprovados. O
relatório sanitizado está em
`benchmarks/qualification/reports/v01-corpus-integrity-v1.json`.

Antes do deploy, o backup `/opt/idml-platform/backups/20260904T200455Z` passou no restore isolado.
A imagem `idml-foundation:phase7-v01-corpus-integrity-v1`
(`sha256:9a3c733134a52cfcd82bf8796c8915e53f179235286505008ab681e0af82471d`)
foi implantada com API, worker e OpenClaw saudáveis. As flags OpenClaw/Swarm permanecem falsas.

## V-02 — Segurança da ingestão IDML

A ingestão passou a validar o ZIP inteiro antes do parser e a falhar fechado para caminhos absolutos
ou ambíguos, travessia, colisões Unicode/casefold, arquivos e diretórios sobrepostos, symlinks,
entradas especiais ou criptografadas, arquivos executáveis e archives aninhados. Limites explícitos
protegem quantidade de entradas, tamanho total expandido, compressão, profundidade e comprimento de
caminho; CRC e mimetype também são conferidos antes da leitura do XML.

O parser XML bloqueia DTD, entidades, resolução externa, documentos malformados e XML individual
acima de 32 MiB. IDML incompleto não falha silenciosamente: referências ausentes no `StoryList`,
frames ligados a stories inexistentes, links de thread quebrados e stories sem frame são
classificados em `reading_order_issues` com evidência quando disponível.

Cancelamento e excesso de tamanho interrompem o upload antes da persistência. Falhas no movimento
atômico removem temporários. O protocolo ClamAV foi testado para resposta limpa, malware, timeout e
resposta indeterminada; indisponibilidade resulta em 503 sanitizado. O ClamAV permanece desligado na
VPS de desenvolvimento e sua ativação operacional será tratada no gate de segurança de produção.

O gate `ops/gate_phase7_v02.py` aprovou 26/26 casos sintéticos e 6/6 IDML reais autorizados sem
emitir conteúdo restrito. A VPS reproduziu os 26 casos em container read-only, sem rede e sem receber
o corpus privado. A suíte integral aprovou 226 testes com 85,29% de cobertura; Ruff e mypy strict
passaram. O relatório sanitizado está em
`benchmarks/qualification/reports/v02-ingestion-security-v1.json`.

Antes do deploy, o backup `/opt/idml-platform/backups/20260908T125309Z` passou no restore isolado
com 21 tabelas públicas, 1 artefato e 14 arquivos do estado OpenClaw. A imagem
`idml-foundation:phase7-v02-ingest-security-v1`
(`sha256:8807135f2d0df6f98a9fe83177ae6cced08c25b7e4ddd4641bf67f08bd59ec15`) deixou API, worker e
OpenClaw saudáveis. As flags OpenClaw, swarm e ClamAV permanecem falsas.

## Decisão

V-01 e V-02 estão aprovados. Isso não aprova o Pacote 7.1, o Gate G7-T ou produção. A próxima família
é V-03, leitura e fidelidade do IDML.
