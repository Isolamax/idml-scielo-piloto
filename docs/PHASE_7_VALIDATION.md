# Fase 7 — Homologação automatizada e piloto simulado

Data inicial: 2026-09-04. Estado: **EM EXECUÇÃO — V-01 A V-06 QUALIFICADOS**.

## Estado das famílias V-01 a V-11

| Família | Estado | Evidência atual |
|---|---|---|
| V-01 Proveniência e integridade | PASSOU | catálogo e gate reproduzível |
| V-02 Segurança da ingestão | PASSOU | matriz negativa, regressão e VPS |
| V-03 Leitura e fidelidade IDML | PASSOU | conservação textual, estrutura e VPS |
| V-04 Canonical Article Model | PASSOU | schemas, invariantes, migrations e round-trip |
| V-05 Construção XML JATS/SPS | PASSOU | builder determinístico, DTD, SPS e referências |
| V-06 Validadores formais | PASSOU COM RESTRIÇÃO | 4 contêineres qualificados; XPM SPS 1.10 aguarda worker Windows |
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

## V-03 — Leitura e fidelidade do IDML

O parser passou a seguir a sequência de spreads declarada no `designmap.xml` e a determinar página
e coluna pela geometria transformada dos pages e frames. A chave de leitura combina página, coluna,
posição vertical/horizontal, thread e `StoryList`, mantendo classificação explícita para referências
incompletas. O modelo Raw preserva as propriedades diretas de parágrafo e caractere, inclusive
negrito, itálico, combinações, sobrescrito e subscrito.

Conteúdo de `Footnote`/`Note`, inclusive texto após processing instructions ACE, agora é separado do
corpo sem duplicação e emitido como `fn-group`. Hyperlinks são associados a todos os runs abrangidos,
inclusive quando o `HyperlinkTextSource` envolve os ranges. O Raw conserva a URL original; na
normalização canônica somente `http`, `https` e `mailto` bem formados viram `ext-link`. Outros
esquemas permanecem auditáveis como texto e geram motivo de revisão. `Bold Italic` vira elementos
JATS aninhados e os valores exatos `BulletList`/`NumberedList` viram listas. Parágrafos e células
vazios permanecem no Raw; a ausência de conteúdo semântico não produz elemento JATS vazio.

O gate `ops/gate_phase7_v03.py` aprovou 10 verificações sintéticas e os seis IDMLs autorizados. A
reconstituição independente do fluxo textual foi exata em 209/209 stories, sem `SequenceMatcher`,
sem chamadas de rede e sem emitir conteúdo restrito. Foram conferidas também páginas, tabelas,
spans, células vazias, notas e cobertura de hyperlinks. A suíte integral aprovou 229 testes, com
85,68% de cobertura, Ruff e mypy strict aprovados. O relatório sanitizado está em
`benchmarks/qualification/reports/v03-idml-fidelity-v1.json`.

Antes do deploy, o backup `/opt/idml-platform/backups/20260908T143455Z` passou no restore isolado
com 21 tabelas públicas, 1 artefato e 14 arquivos do estado OpenClaw. O gate sintético foi
reproduzido na VPS em container read-only e sem rede. A imagem
`idml-foundation:phase7-v03-idml-fidelity-v1`
(`sha256:e614f5dde04a286a896cf837c411df277b497f25533a57c3f265d170e51802b6`)
deixou API, worker e OpenClaw saudáveis. As flags OpenClaw, swarm e ClamAV permanecem falsas.

## V-04 — Canonical Article Model

Os contratos evoluíram para Raw Article 1.3.0 e Canonical Article 1.2.0. As versões anteriores dos
schemas permanecem versionadas e as migrations 1.2→1.3 e 1.1→1.2 são explícitas, não alteram o
objeto de entrada e verificam que cada passo chegou exatamente à versão declarada. Células de tabela
agora têm ID estável; estilos referenciados sem definição no IDML são materializados como
placeholders `unresolved`, preservando o nome da origem sem inventar propriedades.

O Raw rejeita IDs duplicados/vazios, posições de run inválidas, runs ligados a outro story, styles,
frames, tables, cells, notes, objects ou links pendentes, páginas não contíguas, frames sem spread,
thread entre stories e células sobrepostas. A ordem de leitura deve cobrir todos os stories. O
Canonical rejeita campos inline incompatíveis, divergência entre `RichText.plain` e `inlines`, ORCID
com checksum inválido, contributor person/group ambíguo, afiliação duplicada, referência cruzada com
tipo/alvo incorreto, lista/tabela vazia e seção raiz fora do nível 1. IDs inline segmentados passaram
a usar o ID do run, evitando colisão ao redor de fórmulas de bloco.

O gate `ops/gate_phase7_v04.py` aprovou 13 mutações negativas, 128 propriedades Unicode, duas rotas
de migration e round-trip de Raw/Canonical nos seis IDMLs autorizados. O ESA gerou sete seções
canônicas; os cinco RBEdu permaneceram com zero seção sob o profile ESA e motivos explícitos de
revisão, como esperado para corpus de contraste, sem serem promovidos silenciosamente. A suíte
integral aprovou 236 testes com 85,63% de cobertura; Ruff e mypy strict passaram. Relatório:
`benchmarks/qualification/reports/v04-domain-model-integrity-v1.json`.

O backup `/opt/idml-platform/backups/20260908T182615Z` passou no restore isolado com 21 tabelas
públicas, 1 artefato e 14 arquivos OpenClaw. O gate foi reproduzido em container read-only e sem
rede. A imagem `idml-foundation:phase7-v04-model-integrity-v1`
(`sha256:4f46504912f4c5ccfdf46542b2afe28cfe355dfce2875a880d611f9f4834d310`) deixou API, worker e
OpenClaw saudáveis, com OpenClaw, swarm e ClamAV desativados.

## V-05 — Construção XML JATS/SPS

O builder passou a emitir o contrato editorial disponível no Canonical Article: ORCID, prefixo e
sufixo de nome, papéis, e-mail e correspondência ligada por `xref`; afiliação estruturada com
departamento, instituição, ROR e endereço; data ISO estruturada, volume, fascículo, licença e
financiamento; agradecimentos, contribuições, disponibilidade de dados, conflitos, notas e
referências em forma mista e estruturada. O tipo de cada `xref` agora é derivado do alvo registrado,
não de um atributo livre. Declaração UTF-8, DOCTYPE público/sistema e SPS 1.10 são fixos.

O Canonical Article evoluiu para 1.3.0 com `TableCellSpan` e migration aditiva desde 1.2.0. O mapper
leva os spans preservados no Raw até o JATS e o builder gera `rowspan`/`colspan` sem células cobertas
duplicadas. Controles bidirecionais, BOM interno, zero-width space e word joiner permanecem no
Canonical auditável, mas são removidos da serialização para não contaminar o XML.

O validador offline passou a verificar declaração, DOCTYPE, namespaces, idioma, metadados mínimos,
ISSN/DOI, cardinalidade do publisher-id, compatibilidade entre `ref-type` e alvo, gráficos inline e
de bloco, links externos e caracteres invisíveis. O gate `ops/gate_phase7_v05.py` rejeitou 13
mutações negativas, confirmou duas construções idênticas e validou o ESA real com JATS/SPS, zero
referência quebrada e 13 spans preservados. Os cinco RBEdu foram exercitados como contraste: são
bem formados e determinísticos, permanecem reprovados sob o profile ESA e possuem motivos de
revisão explícitos. A suíte integral aprovou 249 testes com 86,11% de cobertura; Ruff passou e mypy
strict foi revalidado após os ajustes finais. Relatório:
`benchmarks/qualification/reports/v05-jats-construction-v1.json`.

O backup `/opt/idml-platform/backups/20260908T195957Z` passou no restore isolado com 21 tabelas
públicas, 1 artefato e 14 arquivos OpenClaw. O gate sintético foi reproduzido na própria imagem em
container read-only, sem rede e sem dependência de `pytest`. A imagem
`idml-foundation:phase7-v05-jats-construction-v1`
(`sha256:5ef4a27be69a7d90c91e1717f38b998473821ccf7b3d52d677e7e080ad2ec4e6`) deixou API, worker,
PostgreSQL, Redis e OpenClaw saudáveis. As flags OpenClaw, swarm e ClamAV permanecem falsas, com
zero `agent_runs`, `agent_proposals` e sessões OpenClaw.

## V-06 — Validadores formais e regras editoriais

Packtools e SPSValidator foram fixados por commit e empacotados em imagens separadas para os canais
ativo e rollback. O registro versionado fixa versão declarada, revisão de origem, ID imutável da
imagem, perfil, comando, timeout e limite de saída. As quatro execuções usam usuário sem privilégio,
filesystem read-only, rede desativada, limites de CPU/memória/processos e `cap-drop=ALL`.

O adaptador aceita somente XML/ZIP limitado, faz parsing seguro, emite um contrato JSON canônico e
sanitiza conteúdo do artigo: permanecem apenas severidades, identidades estáveis das regras,
localizadores em hash, contagens e hashes de evidência. O motor falha fechado para timeout, saída
excessiva ou não UTF-8, JSON inválido, versão/perfil/hash divergentes, severidade desconhecida e
qualquer exceção do validador. Warnings somente podem ser liberados por aceite explícito ligado ao
validador, versão, candidato e código exatos.

O Canonical Article evoluiu para 1.4.0 e o builder passou a representar editora, licença ligada por
URL HTTPS, texto original e código ISO da afiliação, papéis CRediT, histórico editorial, datas de
publicação/coleção, `elocation-id` e modo de disponibilidade dos dados. Isso eliminou as duas
exceções que o SPSValidator inicialmente produzia por ausência de editora e código de licença e
reduziu o candidato sintético de 27 para 1 achado crítico.

As versões ativa e rollback de ambos os validadores concluíram sem exceção. O único crítico
remanescente é um falso positivo reproduzível do próprio Packtools/SPSValidator: a validação de
contribuintes usa o extrator sem enriquecimento de afiliações, embora o mesmo runtime resolva o
`xref/@rid` e a afiliação ao usar `XMLContribs`. Ele permanece visível e **não é dispensado para
release**. Os dois erros remanescentes são verificações externas/semânticas intencionais da fixture
(registro ORCID sem rede e autor de referência ainda não estruturado); nove warnings também não
foram aceitos automaticamente.

O gate `ops/gate_phase7_v06.py` aprovou o registro, atualização/rollback, DTD/SPS offline, contrato
positivo e três mutações negativas, sanitização, empacotamento de gráfico inline, quatro execuções
externas e ingestão do relatório XPM histórico. O XPM 4.0.096 disponível é compatível apenas com SPS
1.9, seu HTML exigiu recuperação controlada e não foi atestado para o candidato; portanto não pode
aprovar release SPS 1.10. A integração definitiva segue reservada ao worker Windows dedicado.
Relatório sanitizado: `benchmarks/qualification/reports/v06-formal-validators-v1.json`.

A suíte integral aprovou 257 testes com 86,44% de cobertura; Ruff, formatação e mypy strict
passaram. Nenhum corpus privado foi enviado à VPS: as execuções externas usaram somente a fixture
sintética sem conteúdo restrito.

## Decisão

V-01 a V-05 estão aprovados e a infraestrutura V-06 está qualificada com a restrição explícita do
XPM/Windows e do defeito conhecido do validador externo. Isso não aprova candidato XML, o Pacote
7.1, o Gate G7-T ou produção. A próxima família é V-07, fidelidade e comparação com referências.
