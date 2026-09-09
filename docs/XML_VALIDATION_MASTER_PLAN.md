# Plano mestre de validação XML e homologação final

Data: 2026-09-01. Estado: **EM EXECUÇÃO — V-01 A V-05 CONCLUÍDOS**.

## 1. Objetivo

Levar a plataforma a uma versão candidata completa e operacionalmente pronta para produção antes
da homologação final por um especialista humano em XML. Durante o desenvolvimento, Codex, agentes
OpenClaw e validadores determinísticos devem encontrar, classificar e corrigir o máximo possível de
defeitos, para que o especialista concentre seu trabalho em decisões editoriais e exceções reais.

"Perfeito" significa, neste plano, zero defeito conhecido bloqueador ou crítico, nenhuma alteração
sem evidência, validações reproduzíveis e todos os riscos residuais declarados. Não significa assumir
que agentes de IA substituem a homologação humana ou que um corpus limitado prova generalização.

## 2. Governança e limites

- O desenvolvimento pode avançar até a prontidão de produção sem baseline humano intermediário.
- Gates técnicos podem ser aprovados por evidência automatizada e multiagente.
- A ativação para tráfego editorial real exige homologação e aceite do especialista em XML.
- Nenhum agente edita diretamente o XML final ou possui autoridade de release.
- Toda proposta permanece vinculada a evidência, schema, versão de prompt/modelo e custo.
- Discordância entre agentes, evidência insuficiente ou baixa confiança resulta em abstenção.
- Regras determinísticas, validadores formais e políticas de release prevalecem sobre agentes.
- Resultados de IA são evidência técnica provisória; não são baseline humano.
- A versão entregue ao especialista deve estar congelada e ser reproduzível.

## 3. Ambientes e conjuntos de dados

### 3.1 Ambientes

1. **Local/CI:** testes unitários, contratos, propriedades, fuzz e golden tests sem segredos.
2. **VPS de desenvolvimento:** integração, OpenClaw controlado, desempenho e recuperação, com os
   serviços atuais isolados e protegidos.
3. **Candidato de homologação:** configuração equivalente à produção, sem tráfego editorial real.
4. **Produção:** somente após o Gate Humano Final e rollout gradual aprovado.

### 3.2 Particionamento do corpus

- `development`: exemplos usados para desenvolver regras e corrigir defeitos.
- `regression`: casos congelados que impedem o retorno de defeitos corrigidos.
- `adversarial`: entradas malformadas, ambíguas, extremas e com prompt injection.
- `holdout-ai`: casos ocultos dos agentes proponentes, usados pelo avaliador automático.
- `holdout-human`: artigos nunca usados em desenvolvimento, reservados ao especialista.

Cada item deve registrar hash, origem, autorização, versão do profile e regras de acesso. O corpus
ESA atual pode iniciar `development`, `regression` e perturbações adversariais, mas não deve ser o
único fundamento da homologação final.

## 4. Arquitetura da validação multiagente

Cada caso será avaliado em sessões separadas, sem compartilhar raciocínio privado:

1. **Proponente:** produz somente proposta tipada com evidência e confiança.
2. **Crítico XML:** procura perda textual, estrutura inválida, invenção e violação SPS/JATS.
3. **Crítico editorial:** procura inconsistências semânticas em metadados, autoria, referências e
   relações entre elementos.
4. **Adjudicador:** recebe entradas e saídas estruturadas, registra concordância ou abstenção e não
   pode aplicar mudanças.
5. **Juiz determinístico:** executa schemas, invariantes, hashes, métricas, validadores e política de
   release. Sua reprovação não pode ser anulada pelos agentes.

Sempre que possível, crítico e adjudicador devem usar versões/prompts independentes. Concordância de
agentes com a mesma origem não será considerada independência estatística; falsos consensos serão
medidos explicitamente.

## 5. Catálogo obrigatório de testes

### 5.1 Responsabilidade de execução

| Família | Executor primário antes da RC | OpenClaw ao vivo | Evidência principal |
|---|---|---:|---|
| V-01 | Codex + verificadores determinísticos | Não | manifestos e hashes |
| V-02 | Codex + suíte de segurança | Não | casos negativos e isolamento |
| V-03 | Codex + críticos OpenClaw | Quando houver ambiguidade | métricas de fidelidade |
| V-04 | Codex + property tests | Não | invariantes e regressões |
| V-05 | Codex + builder/validators | Não | XML e diffs estruturais |
| V-06 | Codex + validadores formais | Não | relatórios JATS/SPS/Packtools/XPM |
| V-07 | Codex + críticos/adjudicador OpenClaw | Sim, nos casos semânticos | métricas e diffs semânticos |
| V-08 | Agentes OpenClaw sob controle do Codex | Sim | propostas, críticas e abstenções |
| V-09 | Codex + testes automatizados de segurança | Não, salvo prompt injection | relatório de segurança |
| V-10 | Codex + automação de interface/API | Opcional e controlado | trilha ponta a ponta |
| V-11 | Codex + fuzz/property/mutation tools | Não | seeds, mutantes e regressões |
| V-12 | Codex + telemetria da VPS | Sim, em janelas orçadas | capacidade, custo e latência |
| V-13 | Codex + automação de recuperação | Não, salvo falha do provider | RPO/RTO e restore |
| V-14 | Codex + auditoria automatizada | Não | métricas, logs e reconstrução |
| V-15 | Codex + pipeline de deploy | Não | smoke, rollback e runbooks |

O especialista humano executará a homologação posterior sobre o `holdout-human`. Antes disso,
Codex responde por planejar, executar, interpretar e documentar os testes; os agentes OpenClaw são
avaliadores restritos, não autoridades do gate.

### V-01 — Proveniência e integridade do corpus

- conferir hashes de IDML, XML, PDF, planilhas, HTML e assets;
- validar autorização, classificação e segregação dos conjuntos;
- detectar arquivo trocado, truncado ou contaminado;
- impedir que o holdout apareça em prompts, fixtures ou logs;
- provar reprodução do mesmo manifesto em local, CI e VPS.

Aceite: 100% dos artefatos rastreáveis e nenhum conteúdo restrito versionado ou exposto.

Evidência: seis manifestos e 21/21 artefatos privados verificados; catálogo sem duplicação ou
contaminação entre splits; holdout ausente de prompts, testes e benchmarks executáveis; fingerprint
canônico reproduzido localmente e na VPS sem rede. Relatório:
`benchmarks/qualification/reports/v01-corpus-integrity-v1.json`.

### V-02 — Segurança da ingestão IDML

- ZIP Slip, symlink, arquivo duplicado e nomes Unicode conflitantes;
- limite de entradas, tamanho expandido, taxa de compressão e profundidade;
- XML externo, DTD externa, entity expansion e conteúdo binário inesperado;
- IDML incompleto, corrompido, com stories órfãos ou referências quebradas;
- cancelamento, timeout e limpeza de temporários.

Aceite: entrada perigosa falha fechada, sem escrita fora do job e sem perda de disponibilidade.

Evidência: 26/26 casos sintéticos e 6/6 pacotes reais aprovados; ZIP/XML validados antes do parser;
referências incompletas classificadas sem falha silenciosa; cancelamento, limites, limpeza de
temporários e indisponibilidade do scanner testados. Gate reproduzido na VPS sem rede e sem corpus
privado. Relatório: `benchmarks/qualification/reports/v02-ingestion-security-v1.json`.

### V-03 — Leitura e fidelidade do IDML

- ordem de leitura por stories, threads, páginas e coordenadas;
- sobrescrito, subscrito, itálico, negrito, links, caracteres especiais e espaços Unicode;
- parágrafos vazios, quebras de linha, tabs, soft hyphen e nonbreaking spaces;
- tabelas com spans, células vazias, notas, listas e conteúdo ancorado;
- imagens, legendas, créditos, equações, notas e material suplementar;
- estilos conhecidos, desconhecidos, ausentes e combinados.

Aceite: nenhuma perda textual não autorizada e toda normalização explicada por regra versionada.

Evidência: o gate independente reconstituiu exatamente 209/209 stories dos seis IDMLs autorizados,
sem emitir conteúdo restrito. O parser segue a ordem de spreads do `designmap.xml`, combina página,
coluna, coordenadas e thread, preserva propriedades diretas de caractere e parágrafo, notas,
hiperlinks, tabelas e vazios. A normalização canônica permite apenas hyperlinks `http`, `https` e
`mailto`; esquemas inseguros permanecem no Raw, são convertidos em texto sem link e geram revisão.
Negrito, itálico, combinações, sobrescrito, subscrito, listas e footnotes possuem regressão JATS.
Relatório: `benchmarks/qualification/reports/v03-idml-fidelity-v1.json`.

### V-04 — Canonical Article Model

- schemas, invariantes, IDs únicos e referências internas resolvidas;
- `RichText.plain` coerente com `inlines` após qualquer patch;
- autores, ORCID, afiliações e correspondência sem associação cruzada indevida;
- seções, listas, citações, notas, figuras, tabelas e referências com cardinalidade correta;
- migrations de versões anteriores e round-trip de serialização;
- property tests para operações idempotentes e ordem estável.

Aceite: 100% dos modelos candidatos válidos e nenhuma referência interna pendente silenciosa.

Evidência: Raw Article 1.3.0 e Canonical Article 1.2.0 publicados com schemas preservando as versões
anteriores e migrations explícitas. O gate rejeitou 13 classes de grafo inválido, aprovou 128 casos
de propriedade Unicode, migrou as duas versões imediatamente anteriores e confirmou round-trip
determinístico nos seis IDMLs autorizados. Estilos desconhecidos viram placeholders auditáveis,
sem definição inventada; células possuem identidade estável. Relatório:
`benchmarks/qualification/reports/v04-domain-model-integrity-v1.json`.

### V-05 — Construção XML JATS/SPS

- XML well-formed e encoding UTF-8;
- namespaces, declaração, ordem, cardinalidade e atributos permitidos;
- front, body, back e subartigos quando aplicável;
- metadados do periódico e artigo, idiomas, datas, licenças e identificadores;
- contribuintes, afiliações, notas de autor e correspondência;
- referências, DOI, links, citações no texto e `xref`/`rid`;
- figuras, tabelas, equações, notas, listas e assets;
- escaping, entidades, caracteres invisíveis e conteúdo misto;
- saída determinística para a mesma entrada e configuração.

Aceite: zero erro de formação, zero referência quebrada e XML determinístico.

Evidência: o builder produz declaração UTF-8 e DOCTYPE JATS Publishing 1.3 fixos, namespaces
XLink/MathML, metadados editoriais, autoria/ORCID/correspondência, afiliações/ROR, datas, licença,
financiamento, back matter, referências mistas e estruturadas e `xref` com tipo derivado do alvo.
O Canonical Article 1.3.0 passou a levar spans de tabela até `rowspan`/`colspan`, com migration
explícita desde 1.2.0. Caracteres invisíveis perigosos são preservados no modelo auditável e
removidos somente na serialização XML. O gate rejeitou 13 mutações negativas e confirmou saída
byte a byte determinística; o ESA real passou JATS/SPS, com 13 spans e zero referência quebrada.
Os cinco RBEdu permaneceram contraste explícito de profile, sem adaptação de regras. Relatório:
`benchmarks/qualification/reports/v05-jats-construction-v1.json`.

### V-06 — Validadores formais e regras editoriais

- validar contra a versão JATS/DTD e o profile SPS fixados;
- executar Packtools e XPM quando aplicável;
- testar regras internas equivalentes para execução offline;
- registrar versão, comando, ambiente, saída sanitizada e hashes;
- transformar cada defeito confirmado em fixture de regressão;
- testar atualização e rollback de versões dos validadores.

Aceite: zero erro bloqueador ou crítico; warnings somente com justificativa e aceite explícitos.

Evidência de qualificação: Packtools 4.17.2 e 4.16.10 e SPSValidator 0.3.0 em duas revisões foram
fixados em quatro imagens imutáveis e executados sem rede, como usuário sem privilégio e em
filesystem read-only. O gate V-06 aprovou contratos positivo/negativos, hash/perfil/versão,
sanitização, limites, atualização/rollback e quatro execuções externas sem exceções. O Canonical
Article 1.4.0 passou a representar os metadados formais confirmados durante o teste. Um falso
positivo crítico de afiliação do extrator de contribuintes externo foi reproduzido e permanece
visível, sem waiver de release. O XPM histórico 4.0.096 é SPS 1.9 e não atesta o candidato SPS 1.10;
a execução definitiva continua pendente do worker Windows dedicado. Assim, os validadores estão
qualificados, mas nenhum candidato XML foi aprovado por esta evidência.
Relatório: `benchmarks/qualification/reports/v06-formal-validators-v1.json`.

### V-07 — Fidelidade e comparação com referências

- Text Fidelity por região e por tipo de conteúdo;
- acurácia de metadados, autores, afiliações, referências e cross-references;
- comparação estrutural consciente de ordem e sem exigir igualdade byte a byte indevida;
- diff semântico entre XML candidato, XML aprovado e conteúdo fonte;
- detecção de omissão, duplicação, deslocamento, invenção e normalização indevida;
- renderização/inspeção visual quando PDF ou HTML forem evidência relevante.

Aceite: 100% dos campos críticos corretos; nenhuma omissão/invenção; divergências não críticas
classificadas e rastreáveis.

### V-08 — Validação assistiva OpenClaw

- executar todos os domínios em casos positivos, negativos, ambíguos e de abstenção;
- medir precisão, recall, exatidão, ganho sobre baseline automático e taxa de abstenção;
- comparar proponente, críticos e adjudicador sem revelar o alvo ao proponente;
- rejeitar evidence hash incorreto, path proibido, schema extra e patch parcial de `RichText`;
- testar alucinação, DOI inexistente, autor inventado e expansão não apoiada;
- testar custo, tokens, latência, timeout e repetição limitada;
- manter tools/Skills vazios nos avaliadores e `needs_human=true` até o aceite final.

Aceite: zero alteração sem evidência, zero violação de contrato, orçamento respeitado e todos os
erros ou desacordos encaminhados como bloqueio/abstenção.

Evidência incremental: a matriz `idml-multi-agent-adversarial-matrix-1.0` cobre seis domínios e cinco
cenários por domínio sem provider. Em 2026-09-01, os 30 casos e 84 papéis simulados passaram 100% dos
oráculos, incluindo invenção com metadados de evidência válidos, ambiguidade, falso consenso e prompt injection. Estrutura e
matemática são sintéticas e continuam exigindo evidência real autorizada antes da RC.

### V-09 — Segurança, identidade e multiempresa

- login, logout, expiração, recuperação, MFA e reautenticação;
- RBAC por empresa, usuário, papel, recurso e ação;
- tentativas de leitura/escrita cruzada entre empresas;
- IDOR, CSRF, XSS, injection, upload malicioso e rate limiting;
- escopo de jobs, artefatos, revisões, auditoria e agentes;
- segredo ausente/rotacionado, logs sanitizados e permissões de arquivos;
- prompt injection em IDML, PDF, XML, metadados e evidências.

Aceite: zero achado crítico/alto aberto e nenhuma possibilidade conhecida de vazamento entre
empresas.

### V-10 — Fluxo ponta a ponta e experiência operacional

- criar empresa/usuário e executar upload, processamento, revisão, aprovação e download;
- reprocessar sem duplicar jobs, propostas, artefatos ou auditoria;
- cancelar, retomar e repetir após falha;
- conferir estados, mensagens, permissões e trilha de auditoria na interface;
- comparar pacote baixado com manifestos e hashes persistidos;
- comprovar operação degradada com OpenClaw desligado.

Aceite: todos os cenários críticos concluídos de forma reproduzível e auditável.

### V-11 — Robustez, propriedades e mutações

- fuzz de XML, ZIP, Unicode, estilos, tabelas e conteúdo misto;
- property tests de idempotência, estabilidade de ordem e preservação de texto;
- metamorphic tests: renomear IDs, reordenar ZIP e variar espaços sem alterar semântica;
- mutation testing nos módulos críticos para verificar a força da suíte;
- regressão automática de cada defeito encontrado por agentes ou especialista.

Aceite: nenhuma falha não controlada e metas de mutação definidas por módulo antes da RC.

### V-12 — Desempenho, capacidade e custo

- artigos pequenos, típicos, grandes e patológicos;
- concorrência inicial e filas sob carga controlada;
- CPU, RAM, swap, disco, I/O, tempo de fila e duração por etapa;
- limites de upload, artefatos, logs, backups e volumes Docker;
- custo de IA por artigo, domínio, reparo e falha;
- teste prolongado para detectar vazamento de memória ou crescimento de estado.

Aceite: nenhuma degradação dos serviços existentes; orçamento respeitado; capacidade documentada e
upgrade da VPS indicado somente por métricas.

### V-13 — Falhas, recuperação e continuidade

- queda de worker, API, PostgreSQL, Redis, OpenClaw, proxy e provider;
- timeout, rate limit, resposta inválida, falta de espaço e processo terminado;
- reinício no meio de ingestão, geração, validação, revisão e pacote;
- backup consistente, checksum, restore isolado e recuperação completa;
- rollback de aplicação, migration, prompt, modelo, profile e configuração;
- exercícios de incident response com tempos medidos.

Aceite: sem corrupção ou perda silenciosa; retomada idempotente; RPO/RTO medidos e aprovados antes
da ativação.

### V-14 — Observabilidade, auditoria e conformidade

- correlação por empresa, usuário, job, versão e artefato;
- métricas e alertas de erro, fila, custo, latência, disco e validação;
- auditoria imutável de decisões humanas e assistivas;
- ausência de segredo, conteúdo restrito e raciocínio privado em logs;
- retenção, exclusão e exportação conforme a política LGPD definida;
- reconstrução completa de quem fez o quê, quando e com qual versão.

Aceite: incidentes e decisões reconstruíveis sem acessar conteúdo indevido.

### V-15 — Deploy e prontidão de produção

- build reproduzível, SBOM/inventário, dependências fixadas e scan de vulnerabilidades;
- migration compatível, smoke test, health/readiness e rollback automático/manual;
- TLS, firewall, headers, secret management e networks privadas;
- rollout gradual, kill switch de IA e modo somente determinístico;
- runbooks executados por outra pessoa ou agente sem conhecimento tácito;
- comparação antes/depois do deploy sem alterar artigos existentes.

Aceite: candidato implantável e reversível, sem ativar tráfego editorial real.

## 6. Metas da versão candidata

- 100% dos testes bloqueadores e críticos aprovados.
- 100% dos XMLs candidatos well-formed e aprovados no schema/profile fixado.
- Zero erro crítico nos validadores externos aplicáveis.
- Zero perda, duplicação ou invenção conhecida de conteúdo.
- Zero `xref`, `rid`, asset ou identificador obrigatório quebrado.
- Zero vazamento entre empresas e zero segredo em código/logs.
- 100% das mudanças assistivas com evidência válida e revisão requerida.
- Suíte global com cobertura mínima de 85%; módulos críticos com meta mínima de 90% e mutation score
  definido antes da RC.
- Pipeline determinístico reproduzível e idempotente.
- Backup, restore, rollback e modo degradado comprovados.
- Nenhum blocker/critical aberto; major somente com correção antes da homologação humana.

As metas de qualidade semântica por domínio serão calculadas no corpus congelado. Uma métrica alta
não compensa uma invenção, perda textual ou violação estrutural crítica.

## 7. Evidências obrigatórias por execução

- manifesto de corpus e configuração;
- commit, imagem, modelo, prompt, schema, profile e versões de validadores;
- casos executados, aprovados, reprovados e abstidos;
- métricas por domínio e tipo de falha;
- custos, tokens, latências e uso de recursos;
- diffs sanitizados e vínculos de evidência;
- logs de backup/restore, rollback e fault injection;
- lista de riscos e defeitos residuais;
- relatório assinado do Gate Técnico correspondente.

## 8. Protocolo de homologação do especialista XML

O especialista receberá somente após a RC completa:

1. ambiente isolado e instruções de uso;
2. corpus `holdout-human` e critérios de amostragem;
3. XMLs, fontes, relatórios de validação e diffs semânticos;
4. matriz de cobertura por domínio e lista de riscos conhecidos;
5. formulário para classificar `blocker`, `critical`, `major`, `minor` e melhoria;
6. mecanismo para reproduzir cada resultado e registrar evidência.

Cada apontamento deve gerar issue rastreável, teste de regressão, correção, reexecução completa e
nova RC. O Gate Humano Final exige zero `blocker`/`critical`, todos os `major` corrigidos e riscos
residuais aceitos explicitamente. Só então a ativação de produção poderá ser autorizada.

## 9. Ordem de execução planejada

1. completar o laboratório multiagente e os casos restantes da Fase 6;
2. automatizar V-01 a V-11 e congelar os corpus de regressão/holdout;
3. executar V-12 a V-15 na Fase 7 e na prontidão 8.1;
4. corrigir até atingir as metas da RC;
5. congelar e entregar a RC ao especialista;
6. incorporar apontamentos com regressão obrigatória;
7. aprovar Gate Humano Final;
8. realizar rollout gradual acompanhado e manter revisão por artigo no período inicial.
