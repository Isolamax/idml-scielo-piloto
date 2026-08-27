# Plano de Desenvolvimento por Fases — Plataforma IDML → XML SciELO

## 1. Finalidade deste documento

Este arquivo controla o planejamento e a execução futura do desenvolvimento da plataforma de conversão IDML para XML SciELO SPS/JATS.

Este documento controla a autorização por fase. Cada fase somente poderá começar após autorização explícita e deverá terminar com evidências verificáveis.

Documento arquitetural de referência:

```text
PLANO_ANALISE_CODEX_SCIELO_IDML_OPENCLAW_SWARM.md
```

## 2. Estado geral

```text
PROJECT_STATUS: PHASE_6_TECHNICAL_EVALUATION_BLOCKED
CURRENT_PHASE: FASE 6 com custo controlado — próximo incremento: gateway OpenClaw dedicado ao IDML
IMPLEMENTATION_AUTHORIZED: PHASE_6_AUTHORIZED — PHASE_7_NOT_AUTHORIZED
PRODUCTION_DEPLOYMENT_AUTHORIZED: NO
ARCHITECTURE_STATUS: APPROVED_WITH_CHANGES
INFRASTRUCTURE_STATUS: IN_USE_WITH_CONSTRAINTS
```

### Legenda de status

- `[ ]` Não iniciado
- `[~]` Em andamento
- `[x]` Concluído e verificado
- `[!]` Bloqueado
- `[-]` Removido do escopo

### Regras de atualização

Ao concluir um item:

1. marcar o checklist;
2. registrar a evidência ou artefato produzido;
3. registrar decisões relevantes em ADR;
4. atualizar riscos e dependências;
5. não aprovar o próprio gate sem validação definida para a fase.

## 3. Princípios obrigatórios

- Parser, aplicação de patches, builder XML, validações formais e empacotamento devem ser determinísticos.
- IA não gera nem edita diretamente o XML final.
- O Canonical Article Model é a fonte estrutural interna.
- Agentes somente propõem operações tipadas e validadas.
- Validadores oficiais e políticas determinísticas controlam o release.
- Swarm deve ser substituível e ativado por feature flag.
- Todo dado relevante deve possuir versão, proveniência e auditoria.
- Nenhum dado ausente pode ser inventado.
- Segurança, testes, persistência e observabilidade são transversais.
- O desenvolvimento não deve ocorrer diretamente no ambiente de produção existente.
- A primeira versão atende um periódico e um template IDML conhecidos.

## 4. Restrições atuais de infraestrutura

Baseline preliminar da VPS HostGator:

```text
SO: Ubuntu 22.04.5 LTS
CPU: 2 vCPUs
RAM: 3,8 GB
Swap em uso na inspeção: 1,3 GB
Disco: 98 GB, 78% utilizado, aproximadamente 21 GB livres
Docker: disponível
Docker Compose: disponível
OpenClaw: 2026.6.11, ativo em container
Reverse proxy: Nginx ativo
Outros serviços: sistema Mapalead, PostgreSQL, Redis e múltiplos workers
```

Decisão:

```text
VPS_USAGE: INITIAL_DEVELOPMENT_AND_PILOT
HARDWARE_UPGRADE: ON_DEMAND
```

A VPS atual será utilizada para iniciar o desenvolvimento, executar os spikes, hospedar o ambiente inicial e realizar o piloto. Os serviços novos devem ser isolados do sistema existente e receber limites de recursos compatíveis com a capacidade disponível.

Não é necessário realizar upgrade preventivo. A necessidade de upgrade será avaliada com base em medições durante o desenvolvimento e o piloto, sem comprometer a disponibilidade do sistema e do OpenClaw já existentes.

Indicadores para avaliar upgrade:

- pressão recorrente de memória ou aumento contínuo de swap;
- CPU sustentada em nível que prejudique os serviços existentes;
- espaço livre em disco insuficiente para artefatos, imagens, volumes e backups;
- aumento relevante da latência ou reinícios por falta de recursos;
- impossibilidade de manter banco, filas e workers isolados;
- crescimento da concorrência ou do volume de artigos;
- necessidade de processamento paralelo de PDF, IDML, validações ou agentes.

Antes de qualquer implantação futura na VPS:

- [x] Criar baseline técnico completo.
- [x] Confirmar backup e testar restauração do ambiente atual.
- [x] Investigar ocupação de disco.
- [x] Criar usuário administrativo não-root.
- [x] Definir diretório e Docker Compose project exclusivos.
- [x] Definir networks, volumes, banco e Redis exclusivos.
- [x] Definir limites de CPU, RAM, disco e concorrência.
- [x] Garantir que nenhum serviço novo seja exposto diretamente à internet.

## 5. Visão das macrofases

| Fase | Nome | Resultado principal | Estado |
|---|---|---|---|
| 0 | Descoberta e viabilidade | Decisão formal GO/NO-GO | Concluída — `GO_WITH_CONSTRAINTS` |
| 1 | Fundação técnica e segurança | Base isolada, persistente e auditável | Concluída — Gate G1 aprovado |
| 2 | Corpus e modelo de domínio | Corpus piloto e modelo canônico estável | Concluída — Gate G2 aprovado |
| 3 | Pipeline determinístico mínimo | IDML → modelo → XML válido sem IA | Concluída — Gate G3 aprovado |
| 4 | Validação, fidelidade e pacote | Pacote validado e política de release | Implementada — Gate G4 bloqueado por validadores externos/crossrefs |
| 5 | Revisão humana e interface mínima | Correção humana auditável | Concluída — Gate G5 aprovado |
| 6 | IA assistiva e OpenClaw | Assistência semântica controlada | Fundação concluída — Gate G6 bloqueado por qualidade/custo/baseline |
| 7 | Homologação e piloto | Qualidade comprovada no periódico piloto | Não iniciada — não autorizada |
| 8 | Produção e operação | Operação segura e recuperável | Não iniciada |
| 9 | Expansão controlada | Novos periódicos e casos complexos | Não iniciada |

---

# FASE 0 — Descoberta e viabilidade

## Objetivo

Eliminar as principais incertezas antes de escrever código de produção.

## Dependências

- Acesso somente leitura à VPS.
- Documentação oficial SciELO vigente.
- Amostras reais do periódico piloto.
- Acesso autorizado às configurações do OpenClaw.

## Pacote 0.1 — Baseline da infraestrutura

- [x] Inventariar SO, CPU, memória, swap, disco e filesystem.
- [x] Inventariar Docker, Compose, networks, volumes e containers.
- [x] Mapear Nginx, domínios, SSL, firewall e portas.
- [x] Mapear persistência, backups, deploy e recuperação atuais.
- [x] Inventariar PostgreSQL, Redis e processos persistentes.
- [x] Inventariar instalação, versão e operação do OpenClaw.
- [x] Identificar consumo de recursos e riscos de coexistência.
- [x] Produzir `docs/ENVIRONMENT_BASELINE.md`.

## Pacote 0.2 — Requisitos oficiais SciELO

- [x] Identificar a versão SPS inicialmente suportada.
- [x] Confirmar JATS/DTD correspondente.
- [x] Confirmar regras de front, body, back e referências.
- [x] Confirmar requisitos de assets e nomes de arquivos.
- [x] Confirmar Packtools, XPM e demais validadores aplicáveis.
- [x] Registrar fontes, versões e data da consulta.
- [x] Produzir `docs/SCIELO_REQUIREMENTS.md`.

## Pacote 0.3 — Spike Packtools

- [x] Selecionar XML oficial ou previamente aprovado.
- [x] Provar execução isolada em Linux.
- [x] Capturar errors e warnings em formato processável.
- [x] Registrar versão, dependências e limitações.
- [x] Não instalar no host sem isolamento aprovado.
- [x] Produzir relatório do spike em `docs/PACKTOOLS_SPIKE.md`.

## Pacote 0.4 — Spike XPM

- [x] Confirmar exigência e função atual do XPM.
- [x] Avaliar execução em Linux/container.
- [x] Avaliar execução headless e formato de resultados.
- [x] Avaliar alternativa com worker Windows dedicado.
- [x] Avaliar licenciamento e automação permitida.
- [x] Produzir `docs/XPM_FEASIBILITY.md`.
- [x] Classificar como `GO_WITH_CONSTRAINTS`.

## Pacote 0.5 — OpenClaw e Swarm

- [x] Registrar versão e método de instalação.
- [x] Confirmar APIs reais de ferramentas e structured output.
- [x] Confirmar suporte real a Swarm, subagents, hooks e schemas.
- [x] Mapear persistência, sessões, retries, timeouts e concorrência.
- [x] Identificar APIs experimentais.
- [x] Definir interface abstrata de orquestração.
- [x] Produzir `docs/OPENCLAW_SWARM_DESIGN.md`.

## Pacote 0.6 — Amostras e IDML

- [x] Selecionar periódico e template piloto.
- [x] Obter IDML, PDF, assets e XML aprovado dos mesmos artigos.
- [x] Inspecionar ZIP, Stories, Spreads, frames, threads e estilos.
- [x] Investigar regras reais de reading order.
- [x] Identificar tabelas, equações, notas, links e objetos ancorados.
- [x] Produzir `docs/IDML_MODEL_ANALYSIS.md`.

## Entregáveis

- `ENVIRONMENT_BASELINE.md`
- `SCIELO_REQUIREMENTS.md`
- `XPM_FEASIBILITY.md`
- `IDML_MODEL_ANALYSIS.md`
- `OPENCLAW_SWARM_DESIGN.md`
- `ARCHITECTURE_REVIEW.md`
- matriz inicial de riscos;
- decisão de infraestrutura.

## Gate de saída G0

- [x] Reading order possui estratégia tecnicamente plausível.
- [x] Versão SPS/JATS inicial foi definida.
- [x] Packtools foi provado ou possui alternativa documentada.
- [x] XPM possui caminho de integração decidido.
- [x] OpenClaw foi auditado sem alteração.
- [x] Corpus piloto foi selecionado.
- [x] Infraestrutura para desenvolvimento foi aprovada.
- [x] Decisão registrada: `GO_WITH_CONSTRAINTS`.

---

# FASE 1 — Fundação técnica e segurança

## Objetivo

Criar a base de desenvolvimento isolada, persistente, segura, observável e testável.

## Dependências

- Gate G0 aprovado.
- Ambiente de desenvolvimento definido na VPS atual, com isolamento e limites de recursos.
- Estratégia de armazenamento aprovada.

## Pacote 1.1 — Repositório e qualidade

- [x] Criar monorepo e convenções de diretórios.
- [x] Definir branching, revisão e proteção de branch.
- [x] Configurar lockfiles e versões de runtime.
- [x] Configurar lint, format, type checking e testes.
- [x] Configurar CI sem acesso a dados de produção.
- [x] Criar templates de issue, ADR e pull request.

## Pacote 1.2 — Ambientes

- [x] Definir development, test, staging e production.
- [x] Criar Compose isolado para desenvolvimento.
- [x] Criar health checks.
- [x] Definir configuração por ambiente.
- [x] Definir feature flags.
- [x] Proibir uso de secrets reais em desenvolvimento.

## Pacote 1.3 — Persistência e artefatos

- [x] Definir PostgreSQL e migrations.
- [x] Definir object/file storage.
- [x] Definir hashes, imutabilidade e retenção de artefatos.
- [x] Definir transações e controle de concorrência.
- [x] Definir backup e restore.
- [x] Definir separação entre versão semântica, execução e tentativa.

## Pacote 1.4 — Identidade e acesso

- [x] Definir Organization, User, Membership, Role e Permission.
- [x] Definir matriz RBAC com negação por padrão.
- [x] Definir autenticação local ou OIDC.
- [x] Definir login, logout, convite e recuperação.
- [x] Definir MFA e reautenticação sensível.
- [x] Definir sessões, expiração, rotação e revogação.
- [x] Definir service accounts.
- [x] Definir isolamento multiempresa no banco, cache, filas e storage.
- [x] Produzir `docs/IDENTITY_AND_ACCESS_MODEL.md`.

## Pacote 1.5 — Estado, jobs e idempotência

- [x] Definir máquina de estados do artigo/job.
- [x] Definir estados retryable, permanent failure e quarantined.
- [x] Definir comandos, eventos e pré-condições de transição.
- [x] Definir idempotency keys.
- [x] Definir retry, backoff, timeout, cancellation e replay.
- [x] Definir retomada após restart.

## Pacote 1.6 — Segurança de ingestão

- [x] Definir limites de upload.
- [x] Proteger contra ZIP bomb e path traversal.
- [x] Impedir symlinks, hardlinks e nested archives não autorizados.
- [x] Configurar XML parser sem XXE e sem rede.
- [x] Validar MIME e conteúdo de assets.
- [x] Isolar parsing por job.
- [x] Definir antivírus/content scanning.
- [x] Definir quarentena.

## Pacote 1.7 — Observabilidade e auditoria

- [x] Definir logs estruturados e correlation IDs.
- [x] Definir métricas de CPU, RAM, disco, fila, latência e custo.
- [x] Definir timeline de jobs.
- [x] Definir security events.
- [x] Impedir secrets e dados desnecessários em logs.
- [x] Definir alertas mínimos.

## Gate de saída G1

- [x] Stack mínimo sobe com health checks.
- [x] Migrations são reproduzíveis.
- [x] Backup e restore foram testados.
- [x] Upload malicioso conhecido é bloqueado.
- [x] Retry não duplica efeitos.
- [x] Usuário não acessa recurso de outra empresa.
- [x] Nenhum serviço interno está exposto publicamente.
- [x] Logs e auditoria permitem reconstruir uma execução.

---

# FASE 2 — Corpus e modelo de domínio

## Objetivo

Construir o corpus de referência e definir modelos independentes de IDML, IA e XML.

## Pacote 2.1 — Corpus gold standard

- [x] Definir licença, confidencialidade e retenção do corpus.
- [x] Anonimizar amostras quando necessário.
- [x] Versionar IDML, PDF, XML e assets.
- [x] Criar ficha de expectativas por artigo.
- [x] Incluir casos simples, limites e documentos problemáticos.
- [x] Definir conjunto de treino interno e conjunto de homologação separado.

## Pacote 2.2 — Raw Article Model

- [x] Representar Stories, frames, threads e coordenadas.
- [x] Representar texto, whitespace, estilos e conteúdo inline.
- [x] Representar links, objetos ancorados, tabelas, notas e assets.
- [x] Preservar referências aos XMLs internos do IDML.
- [x] Definir serialização e compatibilidade de versões.

## Pacote 2.3 — Canonical Article Model

- [x] Modelar front, body e back.
- [x] Modelar contributors, affiliations e correspondência.
- [x] Modelar seções e conteúdo inline sem perda.
- [x] Modelar figuras, tabelas, equações, notas e referências.
- [x] Modelar cross-references e IDs estáveis.
- [x] Separar conteúdo, evidência, decisões e patches.
- [x] Definir estados missing, ambiguous e needs_review.
- [x] Definir migrations de schema.
- [x] Produzir `docs/CANONICAL_ARTICLE_MODEL.md`.

## Pacote 2.4 — Métricas e critérios

- [x] Definir Text Fidelity.
- [x] Definir Metadata, Author e Affiliation Accuracy.
- [x] Definir Reference, Figure e Table Accuracy.
- [x] Definir CrossRef Accuracy.
- [x] Definir tolerâncias de Unicode, espaços e hifenização.
- [x] Definir warnings bloqueadores.
- [x] Definir `NEEDS_REVIEW` versus `FAILED`.
- [x] Definir metas do piloto e STP.

## Gate de saída G2

- [x] Corpus mínimo representa o periódico piloto.
- [x] Modelos serializam e desserializam sem perda.
- [x] IDs permanecem estáveis entre versões.
- [x] Evidências podem ser rastreadas até a fonte.
- [x] Casos não representáveis estão documentados.
- [x] Métricas e limiares foram aprovados antes do parser final.

---

# FASE 3 — Pipeline determinístico mínimo

## Objetivo

Produzir o primeiro XML válido sem IA e sem depender do Swarm.

## Pacote 3.1 — Parser IDML seguro

- [x] Abrir e validar IDML como ZIP não confiável.
- [x] Extrair DesignMap, Stories, Spreads, Styles e Resources.
- [x] Reconstruir threads e relações de frames.
- [x] Implementar estratégia de reading order.
- [x] Extrair texto e estrutura sem IA.
- [x] Extrair assets e registrar proveniência.
- [x] Produzir Raw Article Model.
- [x] Medir cobertura no corpus.

## Pacote 3.2 — Mapeamento canônico

- [x] Criar mapeamento Raw → Canonical.
- [x] Criar Journal Profile piloto.
- [x] Criar style mappings versionados.
- [x] Registrar ambiguidades sem inventar conteúdo.
- [x] Preservar elementos não reconhecidos para auditoria.

## Pacote 3.3 — Builder SPS/JATS

- [x] Implementar builder com árvore XML.
- [x] Implementar front, body e back por componentes.
- [x] Implementar IdRegistry.
- [x] Impedir IDs duplicados e RIDs órfãos.
- [x] Aplicar SpsProfile versionado.
- [x] Gerar XML reprodutível.

## Pacote 3.4 — Validação básica

- [x] Validar well-formed XML.
- [x] Validar DTD/JATS offline e allowlisted.
- [x] Executar regras SPS disponíveis.
- [x] Normalizar resultados dos validadores.
- [x] Produzir relatório processável.

## Gate de saída G3

- [x] Ao menos um artigo real gera XML válido sem IA.
- [x] Pipeline é idempotente.
- [x] Mesmo input e mesmas versões geram resultado equivalente.
- [x] Reading order atinge o limiar definido.
- [x] Nenhum erro é corrigido silenciosamente.
- [x] Falhas são classificadas e auditáveis.

---

# FASE 4 — Validação, fidelidade e pacote

## Objetivo

Comprovar conformidade, fidelidade e integridade do pacote antes de adicionar IA.

## Pacote 4.1 — Validation Engine

- [x] Integrar well-formed, DTD, SPS/Schematron e Packtools/SPSValidator.
- [x] Criar formato único para errors e warnings.
- [x] Implementar regras internas e cross-reference validator.
- [x] Implementar asset validator.
- [x] Registrar versões dos validadores.

## Pacote 4.2 — PDF Fidelity Engine

- [x] Extrair camada textual do PDF quando disponível.
- [x] Usar OCR apenas quando necessário.
- [x] Comparar PDF, modelo canônico e XML.
- [x] Medir título, autores, texto, figuras, tabelas e referências.
- [x] Classificar divergências legítimas e bloqueadoras.

## Pacote 4.3 — Error Classifier e reparos determinísticos

- [x] Classificar deterministic, semantic, missing data, source conflict e system.
- [x] Implementar apenas reparos formalmente seguros.
- [x] Definir limite de ciclos.
- [x] Rebuild e revalidation após cada patch.
- [x] Encaminhar ambiguidades para revisão humana.

## Pacote 4.4 — Package Builder

- [x] Definir layout final do pacote.
- [x] Aplicar regras de nomes de arquivos.
- [x] Verificar presença e hash dos assets.
- [x] Gerar ConversionManifest.
- [x] Tornar releases imutáveis.

## Pacote 4.5 — XPM e Release Policy

- [x] Integrar contrato/parser XPM conforme decisão da Fase 0; executor Windows pendente.
- [x] Criar política determinística de release.
- [x] Definir gates obrigatórios por SpsProfile.
- [x] Impedir que IA conceda `READY_FOR_SCIELO`.
- [x] Registrar override humano permitido e sua justificativa.

## Gate de saída G4

- [x] Pacote é construído antes do gate XPM.
- [ ] Todos os validadores obrigatórios são executados (XPM do candidato pendente).
- [x] Release Policy é versionada e testada.
- [x] ConversionManifest permite auditar a conversão.
- [ ] Corpus determinístico alcança todos os targets e fica sem erros SPS.

---

# FASE 5 — Revisão humana e interface mínima

## Objetivo

Permitir que pessoas autorizadas resolvam ambiguidades no modelo canônico com evidência e auditoria.

## Pacote 5.1 — Fluxo de revisão

- [x] Criar ReviewItem e estados.
- [x] Mostrar evidências de IDML e PDF.
- [x] Mostrar regra, validação e alternativas.
- [x] Aplicar decisão humana como patch.
- [x] Implementar controle de concorrência.
- [x] Reconstruir e revalidar automaticamente.

## Pacote 5.2 — Interface mínima

- [x] Login, logout, recuperação e MFA.
- [x] Seleção e administração de empresa.
- [x] Usuários, convites, papéis e sessões.
- [x] Dashboard de jobs.
- [x] Upload seguro de artigo e assets.
- [x] Timeline de processamento.
- [x] Review Queue.
- [x] Visualização de modelo, XML e validações.
- [x] Diff entre versões.
- [x] Auditoria e download controlado.

## Pacote 5.3 — Aprovação editorial

- [x] Separar permissão de revisão e release.
- [x] Definir ações que exigem MFA/reautenticação.
- [x] Avaliar dupla aprovação.
- [x] Registrar identidade e empresa em todas as decisões.

## Gate de saída G5

- [x] Usuário autorizado corrige uma pendência sem editar XML.
- [x] Usuário não autorizado é bloqueado no backend.
- [x] Patch humano gera nova versão e revalidação.
- [x] Histórico anterior permanece íntegro.
- [x] Auditor consegue reconstruir quem alterou o quê.

---

# FASE 6 — IA assistiva e OpenClaw

## Objetivo

Adicionar IA somente onde houver ganho mensurável sobre o pipeline determinístico e a revisão humana.

## Pacote 6.1 — Contratos de ferramentas

- [x] Definir ferramentas de leitura com menor privilégio.
- [x] Definir `propose_patch` e `validate_patch`.
- [x] Proibir shell, filesystem global e SQL livre.
- [x] Aplicar escopo de job e empresa em todas as ferramentas.
- [x] Produzir `docs/OPENCLAW_TOOL_CONTRACTS.md`.

## Pacote 6.2 — Schemas de saída

- [x] Criar JSON Schemas por domínio.
- [x] Validar saídas antes de qualquer aplicação.
- [x] Definir confidence, evidence, alternatives e reason.
- [x] Rejeitar saída inválida ou sem evidência.
- [x] Exigir patch atômico de `RichText` para `plain.value` e `inlines`.
- [x] Vincular cada operação às evidências exatas e rejeitar evidência declarada sem uso.
- [x] Produzir `docs/AGENT_OUTPUT_SCHEMAS.md`.

## Pacote 6.3 — Orquestração substituível

- [x] Implementar contrato `Orchestrator`.
- [x] Implementar SequentialOrchestrator.
- [x] Implementar TestOrchestrator.
- [x] Implementar SwarmOrchestrator atrás de feature flag.
- [x] Implementar cliente OpenResponses restrito com modelo e agente fixados.
- [x] Definir timeout, retry, custo, cancelamento e concorrência.
- [x] Impedir workers de criar novos Swarms.

## Pacote 6.4 — Domínios assistidos incrementalmente

- [x] Metadata.
- [x] Contributors e affiliations.
- [x] Structure.
- [x] References.
- [x] Figures e tables.
- [x] Math e notes, somente se o piloto exigir (contrato pronto; recurso inativo).
- [ ] Medir cada domínio contra baseline humano.
- [x] Executar proxy técnico provisório no corpus autorizado sem substituir baseline humano.

## Pacote 6.5 — Segurança e avaliação de agentes

- [x] Testar prompt injection proveniente de IDML/PDF.
- [x] Testar saída inválida, timeout e worker crash.
- [x] Testar indisponibilidade OpenAI/OpenClaw.
- [x] Testar patches conflitantes ou atrasados.
- [x] Versionar prompts, Skills, modelos e configurações.
- [x] Deduplicar e limitar o envelope assistivo, registrando seu tamanho canônico.
- [x] Registrar tokens, latência, custo, fonte monetária e versão tarifária sem raciocínio privado.
- [x] Rejeitar a proposta com `COST_UNAVAILABLE` quando provider e catálogo exato não informam custo.
- [x] Fixar tarifa oficial exata para `openai/gpt-5.4-mini`, incluindo entrada em cache.
- [x] Aplicar preflight conservador e orçamento monetário agregado por artigo.
- [!] Isolar o endpoint OpenResponses em gateway dedicado/restrito antes da ativação.

## Pacote 6.6 — QA e repair assistidos

- [ ] Adicionar auditoria assistida somente após baseline.
- [ ] Adicionar repair semântico com limite de ciclos.
- [x] Manter Release Judge apenas consultivo.
- [x] Encaminhar baixa confiança para humano.

## Gate de saída G6

- [x] Desativar Swarm não interrompe o pipeline principal.
- [ ] IA melhora métrica definida sem elevar risco além do limite.
- [x] Nenhum patch é aplicado sem schema, evidência e validação.
- [x] Prompt injection não altera ferramentas ou políticas.
- [x] Orçamento de tokens e custo monetário agregado por artigo é respeitado.
- [x] Release continua sendo determinístico.

---

# FASE 7 — Homologação e piloto

## Objetivo

Validar o sistema completo em corpus separado e operação editorial controlada.

## Pacote 7.1 — Testes completos

- [ ] Unit tests.
- [ ] Golden tests sem exigir igualdade byte a byte quando inadequada.
- [ ] Integration tests.
- [ ] Contract tests de validadores e OpenClaw.
- [ ] Testes de segurança e autorização.
- [ ] Fault injection.
- [ ] Restore e disaster recovery.

## Pacote 7.2 — Homologação do corpus

- [ ] Executar corpus não usado no desenvolvimento.
- [ ] Medir qualidade por tipo de artigo.
- [ ] Comparar resultados com XML aprovado.
- [ ] Classificar falsos positivos e falsos negativos.
- [ ] Medir revisão humana e ciclos de reparo.

## Pacote 7.3 — Piloto editorial

- [ ] Selecionar usuários e responsabilidades.
- [ ] Treinar operadores e revisores.
- [ ] Definir canal de incidentes.
- [ ] Executar artigos reais sem release automático inicial.
- [ ] Obter aceite editorial e técnico.

## Métricas mínimas a reportar

- Text Fidelity.
- Metadata, Author e Affiliation Accuracy.
- Reference, Figure, Table e CrossRef Accuracy.
- Validation Pass Rate.
- Straight Through Processing Rate.
- Human Review Rate.
- Failure Rate.
- Average Repair Passes.
- Average Cost per Article.
- Processing Time.

## Gate de saída G7

- [ ] Métricas mínimas foram atingidas.
- [ ] Não existem bloqueadores de segurança.
- [ ] Restore foi testado.
- [ ] Operação degradada sem IA foi comprovada.
- [ ] Equipe editorial aprovou o fluxo.
- [ ] Capacidade da infraestrutura de produção foi dimensionada.
- [ ] Plano de rollback foi aprovado.

---

# FASE 8 — Produção e operação

## Objetivo

Colocar o piloto aprovado em produção com isolamento, monitoramento e recuperação.

## Pacote 8.1 — Infraestrutura de produção

- [ ] Reavaliar a capacidade da VPS atual com métricas coletadas no piloto.
- [ ] Manter a VPS atual se os critérios operacionais forem atendidos.
- [ ] Realizar upgrade de hardware somente se as medições demonstrarem necessidade.
- [ ] Definir limites e autoscaling possível.
- [ ] Configurar TLS, firewall e redes privadas.
- [ ] Configurar secret management.
- [ ] Configurar storage e backups.
- [ ] Testar restore no ambiente alvo.

## Pacote 8.2 — Deploy

- [ ] Definir pipeline de deploy.
- [ ] Definir migrations compatíveis e rollback.
- [ ] Definir smoke tests.
- [ ] Definir rollout gradual.
- [ ] Manter OpenClaw existente sem atualização não auditada.

## Pacote 8.3 — Operação

- [ ] Criar runbooks.
- [ ] Definir monitoramento e alertas.
- [ ] Definir resposta a incidentes.
- [ ] Definir SLO/SLA operacional.
- [ ] Definir retenção e exclusão LGPD.
- [ ] Definir revisão periódica de acessos.
- [ ] Definir atualização controlada de SPS, dependências e modelos.

## Gate de saída G8

- [ ] Produção aprovada por responsável técnico e editorial.
- [ ] Rollback e restore comprovados.
- [ ] Alertas e runbooks testados.
- [ ] Acessos revisados.
- [ ] Primeiro pacote produzido com acompanhamento humano.
- [ ] Período inicial de operação estabilizado.

---

# FASE 9 — Expansão controlada

## Objetivo

Expandir somente após estabilidade do piloto.

- [ ] Adicionar segundo periódico e novo Journal Profile.
- [ ] Medir regressões no periódico piloto.
- [ ] Adicionar terceiro template.
- [ ] Expandir tabelas complexas e matemática.
- [ ] Expandir suplementos e multimídia.
- [ ] Promover correções recorrentes a regras determinísticas.
- [ ] Validar cada regra candidata antes da promoção.
- [ ] Avaliar generalização para IDML não conhecido.

## Gate de expansão

Cada novo periódico deve possuir corpus, profile, style mapping, métricas, homologação e rollback próprios.

---

# 6. Dependências críticas

| Dependência | Fases afetadas | Plano de contingência |
|---|---|---|
| Documentação SPS vigente | 0–9 | Versionar perfil e bloquear release sem regra confirmada |
| Packtools | 0, 3, 4, 7 | Isolar versão e registrar incompatibilidades |
| XPM | 0, 4, 7, 8 | Worker Windows dedicado, se necessário e permitido |
| Amostras reais | 0–3, 7 | Não congelar modelo/parser sem corpus |
| OpenClaw/Swarm | 0, 6–9 | SequentialOrchestrator e revisão humana |
| OpenAI | 6–9 | Pipeline determinístico e modo degradado |
| Capacidade da VPS | 0–9 | Monitorar, limitar recursos e realizar upgrade quando as métricas demonstrarem necessidade |

# 7. Registro de riscos

| ID | Risco | Impacto | Mitigação | Estado |
|---|---|---|---|---|
| R-01 | Reading order incorreto no IDML | Crítico | Corpus real, frames/threads/coordenadas e revisão visual | Mitigação definida |
| R-02 | XPM não automatizável em Linux | Crítico | Worker Windows dedicado e adapter desacoplado | Mitigação definida |
| R-03 | Regras SPS mudarem | Alto | SpsProfile versionado e testes de regressão | Aberto |
| R-04 | Capacidade da VPS tornar-se insuficiente | Alto | Monitoramento, limites por serviço e upgrade de hardware sob demanda | Monitorado |
| R-05 | Impacto no sistema atual | Crítico | Compose/network/volumes exclusivos e limites | Mitigado e monitorado |
| R-06 | Prompt injection por artigo | Alto | Ferramentas tipadas, conteúdo não confiável e testes | Aberto |
| R-07 | Vazamento entre empresas | Crítico | Escopo no backend, storage isolado e testes negativos | Mitigado na fundação; monitorado |
| R-08 | Modelo canônico insuficiente | Alto | Corpus antes do congelamento e migrations | Mitigado no contrato; validar no parser |
| R-09 | Confiança de IA mal calibrada | Alto | Evidência, agreement, métricas e revisão humana | Aberto |
| R-10 | Custo ou latência excessivos | Médio/Alto | Envelope compacto, tarifa oficial, cache auditado, preflight e teto agregado | Mitigado tecnicamente; monitorar em piloto |
| R-11 | Falha sem retomada idempotente | Alto | Máquina de estados, idempotency keys e recuperação pelo PostgreSQL | Mitigado na fundação; monitorado |
| R-12 | Perda de dados ou histórico | Crítico | Imutabilidade, backups e restore testado | Mitigado na fundação; monitorado |
| R-13 | Vazamento ou contaminação do corpus | Alto | Manifestos sem conteúdo, acesso restrito e holdout separado | Mitigado; monitorado |
| R-14 | Referências sem `xref` bibliográfico | Alto | Detecção offline, CrossRef Accuracy e resolver determinístico de citações | Mitigado tecnicamente — 81 vínculos/52 alvos; seis divergências com o aprovado aguardam adjudicação |
| R-15 | Patch escalar quebrar invariantes de `RichText` | Alto | Patch atômico de `plain` + `inlines` e validação prévia | Mitigado; benchmark v1.3 preparado sem execução de agentes |

# 8. Definition of Done global

Um item somente é considerado concluído quando:

- [ ] implementação e documentação correspondem;
- [ ] critérios de aceite foram testados;
- [ ] testes automatizados relevantes passam;
- [ ] segurança e isolamento foram avaliados;
- [ ] observabilidade foi incluída;
- [ ] versões e dependências foram registradas;
- [ ] não existem secrets em código ou logs;
- [ ] evidências estão vinculadas ao item;
- [ ] riscos residuais estão documentados;
- [ ] revisão necessária foi realizada.

# 9. Critério final de READY_FOR_SCIELO

`READY_FOR_SCIELO` deve ser resultado de política determinística versionada, nunca apenas decisão de um agente.

Condições conceituais:

- [ ] Ingestão segura aprovada.
- [ ] Canonical Article Model válido.
- [ ] Metadados obrigatórios satisfeitos.
- [ ] Fidelidade acima dos limiares.
- [ ] Autores, afiliações e referências resolvidos.
- [ ] Figuras, tabelas, equações e cross-references resolvidos.
- [ ] Assets presentes e íntegros.
- [ ] XML well-formed, JATS/DTD e SPS válidos.
- [ ] Packtools aprovado.
- [ ] XPM aprovado, quando aplicável.
- [ ] Sem ReviewItem bloqueador.
- [ ] Package Builder e ConversionManifest aprovados.
- [ ] Usuário ou processo de release possui autorização válida.
- [ ] Auditoria completa disponível.

# 10. Registro de decisões

Decisões arquiteturais devem ser registradas em:

```text
docs/adr/ADR-NNN-titulo.md
```

ADRs iniciais esperados:

- [x] ADR-001 — versão inicial SPS/JATS.
- [x] ADR-002 — estratégia XPM.
- [x] ADR-003 — ambiente de desenvolvimento e produção.
- [x] ADR-006 — storage de artefatos.
- [x] ADR-007 — fila e execução de jobs.
- [x] ADR-008 — autenticação local ou OIDC.
- [x] ADR-009 — RBAC e isolamento multiempresa.
- [x] ADR-010 — modelos de domínio versionados.
- [x] ADR-011 — governança do corpus e holdout.
- [ ] ADR — estrutura do Canonical Article Model.
- [x] ADR-004 — estratégia de reading order.
- [x] ADR-005 — abstração de orquestração e fallback.
- [x] ADR-012 — política determinística de release.

# 11. Histórico deste plano

| Data | Alteração | Responsável |
|---|---|---|
| 2026-08-24 | Criação do planejamento por fases; nenhuma implementação iniciada | Codex |
| 2026-08-24 | Fase 0 concluída; Gate G0 aprovado como `GO_WITH_CONSTRAINTS`; nenhuma funcionalidade desenvolvida | Codex |
| 2026-08-24 | Fase 1 concluída; Gate G1 aprovado com testes locais e validação ao vivo na VPS; Fase 2 não autorizada | Codex |
| 2026-08-24 | Fase 2 autorizada; corpus, modelos e métricas implementados; Gate G2 em validação | Codex |
| 2026-08-24 | Fase 2 concluída; Gate G2 aprovado localmente e na VPS; Fase 3 não autorizada | Codex |
| 2026-08-24 | Fase 3 autorizada e concluída; parser, profile ESA, builder JATS 1.3 e validação offline implementados; Gate G3 aprovado; Fase 4 não autorizada | Codex |
| 2026-08-24 | Fase 4 implementada; validação/fidelidade/pacote/policy concluídos; Gate G4 bloqueado por erros SPS/editoriais e ausência do XPM do candidato; Fase 5 não autorizada | Codex |
| 2026-08-26 | Fase 5 concluída; revisão humana, interface, identidade/MFA, RBAC e dupla aprovação editorial implementados; Gate G5 aprovado; Gate G4 continua bloqueando release | Codex |
| 2026-08-26 | Fundação da Fase 6 implantada com flags desligadas; agente OpenClaw isolado e benchmark real v1.1 executado; G6 permanece bloqueado por baixa qualidade, custo não observável e ausência de baseline humano | Codex |
| 2026-08-26 | Resolvedor determinístico ESA concluído; 81 vínculos bibliográficos gerados, parser de células corrigido e CrossRef Accuracy incorporada ao G3; seis divergências com o XML aprovado aguardam adjudicação humana | Codex |
| 2026-08-27 | Resolvedor bibliográfico implantado na VPS com backup/restore e rollback; serviços saudáveis e flags de IA mantidas desligadas | Codex |
| 2026-08-27 | Patch atômico de RichText implantado com backup/restore e rollback; prompts 1.1 e benchmark v1.2 preparados; nenhum agente executado e flags mantidas desligadas | Codex |
| 2026-08-27 | Vínculo operação-evidência e envelope compacto implantados; schema 1.1, prompts 1.2 e benchmark v1.3 preparados; nenhum agente executado e flags mantidas desligadas | Codex |
| 2026-08-27 | Política monetária fail-closed implementada e implantada: custo do provider ou tarifa exata versionada, auditoria de proveniência e bloqueio `COST_UNAVAILABLE`; alias real permanece sem preço oficial verificado e flags desligadas | Codex |
| 2026-08-27 | Tarifa oficial do `gpt-5.4-mini` fixada; cache, preflight, teto agregado por artigo e cliente OpenResponses restrito implementados; integração continua desligada até existir gateway dedicado ao IDML | Codex |
