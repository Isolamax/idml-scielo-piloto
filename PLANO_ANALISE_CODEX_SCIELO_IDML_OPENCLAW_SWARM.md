# Projeto: Plataforma Web IDML → XML SciELO SPS/JATS com OpenClaw + Swarm + IA OpenAI

## Documento de handoff para análise no Codex

**Status:** Planejamento técnico inicial aprovado para análise  
**Objetivo desta etapa:** O Codex deve **analisar, auditar e validar a arquitetura antes de escrever código de produção**.  
**Importante:** Não iniciar a implementação completa antes de concluir as validações técnicas, especialmente as relacionadas a SciELO SPS/JATS, Packtools, XPM em Linux, estrutura real de IDML, integração com OpenClaw/Swarm e segurança de arquivos/agentes.

---

# 1. Objetivo do projeto

Construir um sistema **web**, hospedado em ambiente **Linux na HostGator**, capaz de receber arquivos editoriais em IDML e produzir, de forma altamente automatizada, um pacote XML conforme os requisitos da SciELO para indexação/publicação.

O sistema deverá receber, conforme disponibilidade:

- arquivo `.idml`;
- PDF final/prova do artigo;
- imagens;
- tabelas externas;
- material suplementar;
- arquivos multimídia;
- metadados editoriais;
- perfil do periódico/revista.

O sistema deverá produzir:

- XML SciELO SPS/JATS;
- assets organizados;
- pacote final para SciELO;
- relatório de validação;
- relatório de auditoria;
- histórico completo das decisões e correções;
- status final do artigo.

Estados finais esperados:

- `READY_FOR_SCIELO`
- `NEEDS_REVIEW`
- `FAILED`

O estado `READY_FOR_SCIELO` somente poderá ser atribuído quando todos os gates obrigatórios forem aprovados.

---

# 2. Contexto de infraestrutura

## Ambiente previsto

- Plataforma Linux.
- Hospedagem HostGator.
- O servidor já possui **OpenClaw instalado e funcionando**.
- O sistema será novo, sem legado de aplicação a preservar.
- A arquitetura pode utilizar tecnologias experimentais quando houver ganho técnico real, desde que exista isolamento e fallback.
- A utilização de **OpenClaw Swarm** desde a primeira versão foi aprovada como decisão arquitetural.
- A aplicação web deverá ser containerizada quando isso fizer sentido.
- O OpenClaw existente não deve ser alterado, atualizado ou migrado sem auditoria e backup prévios.

## Premissa que o Codex deve confirmar

Assumimos que a hospedagem HostGator utilizada é VPS/servidor Linux com:

- acesso SSH;
- permissões suficientes;
- Docker/Compose disponíveis ou instaláveis;
- possibilidade de rodar processos de backend e workers persistentes.

**O Codex deve validar isso antes de qualquer implementação.**

Se o ambiente for hospedagem compartilhada ou tiver limitações incompatíveis, registrar o impacto e propor arquitetura alternativa.

---

# 3. Decisão arquitetural principal

A arquitetura NÃO deve ser:

```text
IDML → LLM → XML → validação
```

A arquitetura aprovada é:

```text
IDML
  ↓
Parser determinístico
  ↓
Raw Article Model
  ↓
Canonical Article Model
  ↓
OpenClaw + Swarm + agentes especializados
  ↓
Canonical Article Model revisado
  ↓
Builder SPS/JATS determinístico
  ↓
XML
  ↓
DTD / SPS / Packtools / regras internas
  ↓
Repair pipeline
  ↓
QA
  ↓
XPM / Package Gate
  ↓
READY_FOR_SCIELO
```

## Princípio central

> **OpenClaw decide e coordena. Python executa. Os validadores SciELO determinam conformidade.**

---

# 4. Regras arquiteturais obrigatórias

## 4.1 A IA não gera o XML final diretamente

Modelos de IA não devem produzir o arquivo XML final como texto livre.

A IA deverá trabalhar sobre dados estruturados e produzir:

- classificações;
- interpretações;
- propostas de alteração;
- decisões estruturadas;
- resultados aderentes a JSON Schema.

O XML deve ser produzido por código determinístico.

---

## 4.2 Agentes não editam XML diretamente

Agentes devem propor operações estruturadas.

Exemplo conceitual:

```json
{
  "operation": "set_author_affiliation",
  "author_id": "author-003",
  "affiliation_ids": ["aff-002"],
  "confidence": 0.994,
  "reason": "Afiliação indicada pelo sobrescrito e pela ordem visual",
  "evidence": [
    {
      "source": "idml",
      "story_id": "Story_u123",
      "paragraph_id": "p17"
    }
  ]
}
```

O backend:

1. valida a operação;
2. aplica ao Canonical Article Model;
3. gera uma nova versão do modelo;
4. reconstrói o XML;
5. executa validação novamente.

---

## 4.3 Não permitir alterações destrutivas sem versionamento

Nunca sobrescrever o estado anterior.

Manter versões:

```text
Article Model v1
Article Model v2
Article Model v3
...
```

O mesmo vale para:

- XML;
- patches;
- relatórios;
- resultados de agentes;
- validações;
- pacotes.

---

## 4.4 Toda informação deve possuir proveniência

Sempre que possível, armazenar:

- origem;
- posição;
- método de extração;
- agente responsável;
- confiança;
- versão;
- evidência.

Exemplo:

```json
{
  "value": "Silva",
  "confidence": 0.998,
  "status": "confirmed",
  "source": {
    "type": "idml",
    "story_id": "Story_u123",
    "paragraph": 17,
    "character_range": [4, 9]
  },
  "created_by": "metadata-worker",
  "revision": 4
}
```

---

## 4.5 IA não pode inventar dados ausentes

Quando não houver evidência suficiente:

```text
MISSING
```

ou:

```text
NEEDS_REVIEW
```

Nunca preencher por suposição.

---

## 4.6 Hierarquia de autoridade

Quando houver conflito, seguir a seguinte ordem:

1. especificação SciELO SPS aplicável;
2. JATS/DTD aplicável;
3. Packtools;
4. XPM;
5. regras determinísticas internas;
6. dados extraídos do IDML/PDF;
7. decisões de agentes.

A maioria dos agentes não pode prevalecer contra uma regra formal.

---

## 4.7 Versionamento das regras SciELO

Não hardcodar `latest`.

Criar conceito como:

```text
SPS_PROFILE
```

ou:

```text
SpsProfile
```

que determine:

- versão SPS;
- versão JATS;
- DTD;
- Schematron, se aplicável;
- regras;
- elementos obrigatórios;
- atributos;
- convenções;
- validações;
- regras de pacote.

Toda conversão deve registrar a versão utilizada.

---

## 4.8 Controle de acesso, empresas e usuários

O sistema deve ser multiempresa desde a modelagem inicial, ainda que a primeira implantação atenda apenas uma empresa.

Conceitos mínimos:

- `Organization` ou `Company`: empresa/cliente responsável pelos periódicos e artigos;
- `User`: identidade humana com login individual;
- `Membership`: vínculo entre usuário e empresa;
- `Role`: conjunto de permissões dentro de uma empresa;
- `ServiceAccount`: identidade não humana para integrações e workers, quando necessário;
- `Session`: sessão autenticada, revogável e auditável.

Um usuário poderá pertencer a mais de uma empresa, com papéis diferentes em cada uma. Nenhuma autorização deve depender apenas de dados enviados pelo frontend.

Papéis iniciais sugeridos:

```text
SYSTEM_ADMIN
ORGANIZATION_ADMIN
JOURNAL_MANAGER
EDITOR
REVIEWER
OPERATOR
AUDITOR
VIEWER
```

O Codex deve revisar esses papéis e propor uma matriz de permissões. Evitar regras espalhadas no código; preferir RBAC centralizado, com restrições por recurso quando necessário.

Permissões mínimas a distinguir:

- administrar empresa, usuários e convites;
- criar e editar periódicos e seus perfis;
- enviar e processar artigos;
- visualizar fontes e dados potencialmente confidenciais;
- revisar pendências e aplicar patches;
- aprovar ou bloquear release;
- baixar XML e pacotes;
- consultar auditoria;
- administrar configurações globais.

Todo recurso de negócio deve possuir `organization_id` ou vínculo equivalente, incluindo periódicos, artigos, jobs, arquivos, modelos, patches, validações e pacotes.

Requisitos obrigatórios:

- isolamento entre empresas no backend, banco e storage;
- menor privilégio e negação por padrão;
- login individual, sem contas compartilhadas;
- senhas armazenadas com algoritmo moderno, caso autenticação local seja utilizada;
- sessões seguras, expiração, logout e revogação;
- recuperação de senha com tokens curtos, de uso único e sem revelar a existência da conta;
- verificação de e-mail e fluxo seguro de convite;
- rate limiting e proteção contra enumeração e brute force;
- MFA obrigatório para administradores e recomendado para demais papéis;
- reautenticação para ações sensíveis;
- trilha de auditoria de login, falhas, mudanças de papel, convites, revogações e acessos sensíveis;
- bloqueio ou desativação de usuário sem apagar seu histórico;
- política de retenção para sessões e eventos de segurança.

Avaliar integração com provedor de identidade via OIDC/OAuth 2.0 em vez de implementar autenticação completa internamente. SSO empresarial pode ser acrescentado conforme necessidade, sem acoplar a autorização ao provedor externo.

### Regra

Autenticação responde **quem é o usuário**. Autorização determina **o que ele pode fazer em uma empresa e recurso específicos**. As duas responsabilidades devem permanecer separadas.

### Entregável

```text
docs/IDENTITY_AND_ACCESS_MODEL.md
```

---

# 5. Arquitetura alvo

```text
                       INTERNET
                           │
                           ▼
                  Reverse Proxy / SSL
                           │
                           ▼
              ┌────────────────────────┐
              │        WEB APP         │
              │       Next.js          │
              └────────────┬───────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │        FastAPI         │
              │       REST API         │
              └────────────┬───────────┘
                           │
       ┌───────────────────┼────────────────────┐
       │                   │                    │
       ▼                   ▼                    ▼
   PostgreSQL            Redis             Object/File
       │                   │                 Storage
       │                   ▼                    │
       │              Job Workers               │
       │                   │                    │
       │                   ▼                    │
       │          ┌──────────────────┐           │
       │          │  SciELO Engine   │◄──────────┘
       │          │ Python / lxml    │
       │          └────────┬─────────┘
       │                   │
       │                   ▼
       │            OpenClaw Gateway
       │                   │
       │                   ▼
       │             Swarm Supervisor
       │                   │
       │      ┌────────────┼─────────────┐
       │      ▼            ▼             ▼
       │  Metadata     References     Structure
       │      │            │             │
       │      ▼            ▼             ▼
       │  Figures      Tables/Math    QA Agents
       │      └────────────┼─────────────┘
       │                   │
       │                   ▼
       │        Canonical Article Model
       │                   │
       │                   ▼
       │          SPS/JATS XML Builder
       │                   │
       │                   ▼
       │       DTD + SPS + Packtools
       │                   │
       │                   ▼
       │                  XPM
       │                   │
       └───────────────────┤
                           ▼
                  READY_FOR_SCIELO
```

---

# 6. Stack técnica inicialmente recomendada

O Codex deve validar se há razão técnica para substituir algum componente.

## Backend

- Python
- FastAPI
- Pydantic
- lxml
- Packtools
- SQLAlchemy
- Alembic
- PostgreSQL
- Redis
- Celery ou alternativa equivalente

## Frontend

- Next.js
- TypeScript
- React

## IA e orquestração

- OpenClaw existente
- OpenClaw Code Mode, se compatível
- OpenClaw Swarm
- OpenAI models
- Structured Outputs / JSON Schema
- ferramentas OpenClaw tipadas
- Skills OpenClaw

## Infra

- Linux
- Docker
- Docker Compose
- reverse proxy
- HTTPS / Let's Encrypt
- PostgreSQL
- Redis
- armazenamento persistente
- sistema de backup

---

# 7. O que o Codex deve fazer ANTES de escrever código de produção

Esta seção é obrigatória.

O Codex deve primeiro produzir um **parecer técnico**.

Não iniciar o desenvolvimento completo sem responder aos itens abaixo.

---

## 7.1 Auditar o servidor existente

Levantar:

- distribuição Linux;
- kernel;
- CPU;
- RAM;
- swap;
- disco;
- espaço disponível;
- filesystem;
- Docker;
- Docker Compose;
- containers existentes;
- networks Docker;
- volumes;
- portas;
- reverse proxy;
- SSL;
- firewall;
- Python;
- Node;
- npm/pnpm/yarn;
- PostgreSQL existente;
- Redis existente;
- processos persistentes;
- backups;
- método de deploy atual.

### OpenClaw

Identificar:

- versão;
- forma de instalação;
- usuário que executa;
- diretórios;
- configuração;
- gateway;
- plugins;
- Skills;
- modelos;
- conexões;
- logs;
- portas;
- persistência;
- forma de atualização.

Confirmar compatibilidade da versão instalada com:

- Swarm;
- Code Mode;
- subagents;
- structured output;
- tool plugins;
- JSON Schema;
- hooks;
- políticas de ferramentas.

### Regra

**Não atualizar OpenClaw ainda.**

Antes de qualquer atualização:

- backup;
- cópia de configuração;
- versão atual registrada;
- plugins registrados;
- Skills registrados;
- credenciais protegidas;
- rollback documentado.

### Entregável

```text
docs/ENVIRONMENT_BASELINE.md
```

---

## 7.2 Validar a documentação SciELO atual

O Codex deve consultar a documentação oficial vigente e responder:

- qual versão do SciELO Publishing Schema deve ser inicialmente suportada;
- qual JATS/DTD corresponde;
- quais validadores são atualmente exigidos/recomendados;
- papel atual do Packtools;
- papel atual do XML Package Maker;
- requisitos atuais para empacotamento;
- requisitos de nomes de arquivos;
- regras de assets;
- regras de referências;
- requisitos de front/body/back;
- requisitos de metadados;
- diferenças relevantes entre versões SPS.

Não confiar apenas neste documento para regras formais.

**A documentação oficial vigente é a fonte de verdade.**

---

## 7.3 Provar Packtools no Linux

Criar um spike técnico isolado.

O Codex deve demonstrar:

```text
XML de referência
      ↓
Packtools
      ↓
relatório estruturado
```

Precisamos conseguir:

- validar XML;
- capturar erros;
- capturar warnings;
- gerar saída processável por máquina;
- registrar versão do Packtools.

---

## 7.4 Provar XPM no ambiente real

Este é um dos maiores riscos técnicos.

O Codex deve confirmar:

- se o XML Package Maker pode ser executado de modo confiável em Linux;
- se pode operar headless;
- dependências;
- limitações;
- licenças;
- modo de integração;
- formato dos relatórios;
- estabilidade;
- possibilidade de containerização.

Avaliar, nesta ordem:

### Opção A

XPM rodando diretamente em Linux/container.

### Opção B

XPM executado via camada de compatibilidade tecnicamente confiável.

### Opção C

Worker Windows dedicado, chamado por API/fila.

Exemplo:

```text
Linux Web Platform
       │
       ▼
Validation Queue
       │
       ▼
Windows XPM Worker
       │
       ▼
Validation Result
```

### Regra

Não substituir silenciosamente XPM por validador próprio se a documentação SciELO vigente ainda exigir XPM.

### Entregável

```text
docs/XPM_FEASIBILITY.md
```

com conclusão:

```text
GO
```

ou:

```text
GO_WITH_CONSTRAINTS
```

ou:

```text
NO_GO
```

e proposta de solução.

---

## 7.5 Analisar amostras reais de IDML

Antes de projetar o parser final, o Codex deve inspecionar arquivos IDML reais.

Analisar:

- estrutura ZIP;
- Stories;
- Spreads;
- DesignMap;
- Resources;
- Styles;
- Links;
- Fonts;
- MasterSpreads;
- XML internos;
- threading;
- TextFrames;
- paragraph styles;
- character styles;
- object styles;
- anchored objects;
- tables;
- images;
- equations;
- footnotes;
- endnotes;
- hyperlinks;
- cross-references.

Responder especialmente:

### Como determinar a ordem editorial correta?

A ordem dos arquivos internos não deve ser assumida como ordem de leitura.

Precisamos investigar:

- relações story/frame;
- threads;
- spreads;
- páginas;
- coordenadas;
- linked text frames;
- anchored objects.

### Entregável

```text
docs/IDML_MODEL_ANALYSIS.md
```

---

## 7.6 Projetar o Canonical Article Model antes do parser

Não implementar o parser acoplado diretamente ao XML SciELO.

Primeiro definir o modelo canônico.

O Codex deve propor schemas para:

- Article
- Journal
- Issue
- ArticleMeta
- Titles
- Contributors
- Authors
- Affiliations
- Correspondence
- Abstracts
- Keywords
- Sections
- Paragraphs
- Inline content
- Lists
- Quotes
- Figures
- Tables
- Equations
- Footnotes
- References
- Acknowledgements
- Funding
- Permissions
- Supplementary material
- Media
- Cross references

Cada elemento importante deverá poder guardar:

- ID interno estável;
- conteúdo;
- origem;
- confiança;
- status;
- autor da decisão;
- evidência;
- revisão;
- timestamps.

### Estados sugeridos

- `extracted`
- `inferred`
- `confirmed`
- `ambiguous`
- `missing`
- `rejected`
- `needs_review`

### Entregável

```text
docs/CANONICAL_ARTICLE_MODEL.md
```

e schemas iniciais.

---

## 7.7 Projetar os contratos de ferramentas OpenClaw

Antes de escrever Skills/agentes, definir as ferramentas.

Exemplos:

```text
get_article_summary
get_source_fragment

get_metadata
get_contributors
get_affiliations

get_sections
get_section

get_references
get_reference

get_figures
get_tables
get_equations

propose_patch
validate_patch

run_validation
get_validation_errors

compare_source
get_review_items
```

Agentes devem operar por APIs tipadas.

### Regra

Agentes NÃO devem receber shell ou filesystem arbitrário por padrão.

### Entregável

```text
docs/OPENCLAW_TOOL_CONTRACTS.md
```

---

## 7.8 Projetar schemas dos resultados dos agentes

Nenhum agente crítico deve retornar apenas texto livre.

Criar JSON Schemas para:

- MetadataResult
- ContributorResult
- AffiliationResult
- StructureResult
- ReferenceResult
- FigureResult
- TableResult
- MathResult
- FidelityResult
- QAResult
- RepairProposal
- ReleaseDecision

### Entregável

```text
docs/AGENT_OUTPUT_SCHEMAS.md
```

---

## 7.9 Analisar a arquitetura Swarm

O Codex deve validar:

- API real disponível na versão instalada;
- capacidade de structured output;
- concorrência;
- timeouts;
- retry;
- limites;
- observabilidade;
- custo;
- comportamento quando worker falha;
- retomada de jobs;
- modelo de sessão;
- isolamento entre agentes.

### Decisão aprovada

Começar com Swarm desde a V1.

### Porém

O core SciELO não pode depender semanticamente do Swarm.

Criar interface de orquestração:

```text
Orchestrator
    ├── SwarmOrchestrator
    ├── SequentialOrchestrator
    └── TestOrchestrator
```

Assim, se a interface experimental mudar, o sistema continua operando.

### Evitar

Swarms aninhados sem controle.

Arquitetura desejada:

```text
Supervisor
   ↓
Swarm
   ↓
Workers leaf
```

Workers não devem criar novos Swarms.

---

# 8. Fases de desenvolvimento propostas

---

# FASE 0 — Baseline e auditoria

## Objetivo

Entender o servidor existente sem alterar o ambiente.

## Entregáveis

- `ENVIRONMENT_BASELINE.md`
- mapa da infraestrutura;
- inventário OpenClaw;
- riscos;
- plano de backup/rollback.

## Gate

Nenhuma alteração destrutiva antes da aprovação do baseline.

---

# FASE 1 — Monorepo e ambiente isolado

Estrutura sugerida:

```text
scielo-ai/
│
├── frontend/
│   └── web/
│
├── backend/
│   ├── api/
│   ├── workers/
│   └── scielo_engine/
│
├── openclaw/
│   ├── agents/
│   ├── skills/
│   ├── plugins/
│   ├── swarms/
│   └── schemas/
│
├── schemas/
│   ├── canonical/
│   ├── sps/
│   └── operations/
│
├── rules/
│   └── sps/
│
├── tests/
│   ├── fixtures/
│   ├── idml/
│   ├── xml/
│   └── golden/
│
├── infra/
│   ├── docker/
│   └── compose/
│
└── docs/
```

Ambientes:

- development
- staging
- production

Fundação obrigatória desta fase:

- persistência e migrations;
- identidade de empresa e usuário;
- autenticação e sessões;
- autorização centralizada;
- isolamento multiempresa;
- trilha de auditoria;
- observabilidade mínima;
- gestão segura de secrets.

## Gate

Subir stack mínimo com health checks e provar, por testes automatizados, que um usuário autenticado não consegue acessar recursos de outra empresa.

---

# FASE 2 — Spike SciELO / Packtools / XPM

## Objetivo

Eliminar riscos externos cedo.

## Entregáveis

- Packtools funcionando;
- versão registrada;
- relatório estruturado;
- conclusão XPM/Linux;
- primeiro pacote de referência validado.

## Gate

Não avançar para automação completa sem compreender claramente a validação final.

---

# FASE 3 — Canonical Article Model

## Objetivo

Criar a representação semântica independente de IDML, IA e XML.

## Gate

Serialização/deserialização estável.

Nenhum dado deve se perder ao salvar/carregar.

---

# FASE 4 — Parser IDML determinístico

## Objetivo

Extrair o máximo possível sem IA.

Extrair:

- texto;
- estilos;
- estrutura;
- frames;
- threading;
- imagens;
- links;
- tabelas;
- objetos;
- notas;
- posição.

Produzir:

```text
RawArticleModel
```

e depois mapear para o modelo canônico.

## Métrica

Para corpus conhecido:

- cobertura textual;
- cobertura de figuras;
- cobertura de tabelas;
- cobertura de estilos;
- ordem de leitura.

---

# FASE 5 — Segurança de ingestão

Implementar antes de permitir uploads externos reais.

Ver seção de segurança deste documento.

---

# FASE 6 — Builder SPS/JATS determinístico

Criar builders independentes:

```text
article
front
journal-meta
article-meta
contrib-group
aff
abstract
kwd-group
body
sec
fig
table-wrap
disp-formula
ref-list
back
```

Usar árvore XML, preferencialmente `lxml`.

Nunca concatenar strings para gerar XML.

Criar `IdRegistry`.

O registry deve impedir:

- ID duplicado;
- RID órfão;
- referências cruzadas inválidas.

## Gate

Gerar primeiro XML válido sem IA.

Esse é um marco obrigatório.

---

# FASE 7 — Journal Profiles

Criar perfis por periódico.

Armazenar:

- título;
- ISSN;
- eISSN;
- publisher;
- acrônimo;
- idioma;
- licença;
- SPS profile;
- seções;
- defaults;
- template IDML;
- style mappings.

Exemplo:

```text
ART_TIT  → article-title
AUT      → contrib
AFF      → affiliation
RES      → abstract
KW       → keywords
H1       → sec level 1
H2       → sec level 2
BODY     → p
CAP_FIG  → fig caption
REF      → reference
```

Objetivo:

Quanto mais consistente o template da revista, menos IA utilizar.

---

# FASE 8 — OpenClaw Tool Plugin / integração

Conectar OpenClaw ao SciELO Engine.

Agentes apenas recebem ferramentas necessárias.

Aplicar princípio de menor privilégio.

---

# FASE 9 — Skills SciELO

Estrutura proposta:

```text
openclaw/skills/
├── sps-core/
├── metadata/
├── affiliations/
├── structure/
├── references/
├── figures/
├── tables/
├── math/
├── fidelity/
├── repair/
└── release/
```

Cada Skill deve ser:

- curta;
- focada;
- versionada;
- testável;
- vinculada à versão SPS quando necessário.

---

# FASE 10 — Agentes base

Criar pelo menos:

```text
scielo-supervisor
scielo-worker
scielo-judge
```

Depois especializações.

---

# FASE 11 — Semantic Extraction Swarm

Swarm paralelo para:

- metadata;
- contributors;
- affiliations;
- body structure;
- figures;
- tables;
- math;
- footnotes;
- references.

Começar conservadoramente com concorrência limitada.

Exemplo inicial:

```text
maxConcurrent = 8
```

Validar na infraestrutura real.

Toda saída deve seguir schema.

---

# FASE 12 — Reference Swarm

Dividir referências em chunks.

Exemplo:

```text
1–30
31–60
61–90
91–120
```

Cada worker estrutura referências.

Depois outro agente audita.

Cruzar:

```text
body citations ↔ ref-list
```

Detectar:

- `citation_without_reference`
- `reference_without_citation`
- `ambiguous_reference`

---

# FASE 13 — PDF Fidelity Engine

O PDF deve ser usado como fonte independente de auditoria.

Comparar:

```text
PDF
↕
Canonical Article Model
↕
XML
```

Itens:

- título;
- autores;
- afiliações;
- seções;
- texto;
- figuras;
- tabelas;
- legendas;
- referências;
- notas.

Criar métricas determinísticas sempre que possível.

---

# FASE 14 — QA Swarm adversarial

Criar agentes cuja função seja procurar erros, não apenas confirmar o trabalho anterior.

Sugestão:

```text
Fidelity Auditor
Metadata Auditor
Reference Auditor
Structure Auditor
CrossRef Auditor
Asset Auditor
```

Depois:

```text
QA Adjudicator
```

---

# FASE 15 — Validation Engine

Pipeline:

```text
XML
 ↓
well-formed
 ↓
DTD
 ↓
SPS/Schematron
 ↓
Packtools
 ↓
internal rules
 ↓
cross-reference validator
 ↓
asset validator
```

Normalizar todo erro:

```json
{
  "validator": "packtools",
  "severity": "error",
  "code": "...",
  "xpath": "...",
  "message": "...",
  "repair_type": "semantic"
}
```

---

# FASE 16 — Error Classifier

Categorias:

- `DETERMINISTIC`
- `SEMANTIC`
- `MISSING_DATA`
- `SOURCE_CONFLICT`
- `SYSTEM`

Somente o que exigir raciocínio deve ir para IA.

---

# FASE 17 — Repair Swarm

Fluxo:

```text
Validation errors
      ↓
Classifier
      ↓
 ┌───────────────┐
 │ deterministic │ → Python
 └───────────────┘

 ┌───────────────┐
 │ semantic      │ → Repair Swarm
 └───────────────┘
      ↓
patch
      ↓
Canonical Article Model
      ↓
rebuild
      ↓
validate
```

Limitar ciclos.

Sugestão inicial:

```text
max_repair_passes = 4
```

Após o limite:

```text
NEEDS_REVIEW
```

---

# FASE 18 — Human Review

A revisão humana atua no modelo canônico, nunca diretamente no XML.

A interface deve mostrar:

- problema;
- evidência do IDML;
- evidência do PDF;
- decisão dos agentes;
- confiança;
- opções;
- histórico.

A decisão humana gera patch.

Depois:

- nova versão;
- rebuild;
- revalidation.

---

# FASE 19 — Interface Web

Telas mínimas:

## Acesso

- Login
- Logout
- Recuperação e redefinição de senha
- Verificação de e-mail
- MFA
- Sessões ativas e revogação
- Seleção de empresa, quando o usuário pertencer a mais de uma

## Administração da empresa

- Dados da empresa
- Usuários
- Convites
- Papéis e permissões
- Usuários ativos, bloqueados e desativados
- Eventos de segurança e auditoria

## Dashboard

- Jobs
- Processing
- Ready
- Needs Review
- Failed

## Journals

- Profiles
- Templates
- Style mappings

## New Article

- IDML
- PDF
- Assets
- Journal
- Metadata

## Processing

Timeline:

- ingestão;
- parser;
- semantic swarm;
- references;
- XML;
- validation;
- repairs;
- QA;
- XPM.

## Review Queue

Pendências.

## Article

- metadata;
- model;
- XML;
- files.

## Diff

Comparar versões.

## Validation

Packtools / SPS / XPM / internal.

## Audit

Histórico completo.

## Release

Gerar pacote.

---

# FASE 20 — Release Swarm

Agentes independentes:

- Fidelity Judge
- Metadata Judge
- Reference Judge
- Package Judge

Depois:

```text
Release Adjudicator
```

Esse agente NÃO pode alterar dados.

Só aprovar ou bloquear.

Saída:

```json
{
  "release": true,
  "blocking_issues": [],
  "warnings": []
}
```

---

# FASE 21 — XPM Release Gate

Se a documentação SciELO vigente confirmar XPM como obrigatório, ele deve ser gate final.

`READY_FOR_SCIELO` exige todos os validadores obrigatórios.

---

# FASE 22 — Package Builder

Gerar:

- XML;
- PDF;
- figures;
- tables/assets;
- supplementary;
- media;
- relatórios;
- pacote final.

Aplicar nomes de arquivos exatamente conforme regras vigentes.

---

# FASE 23 — Persistência

Entidades inicialmente sugeridas:

```text
users
organizations
organization_memberships
roles
permissions
role_permissions
user_role_assignments
invitations
user_sessions
password_reset_tokens
email_verification_tokens
mfa_methods
service_accounts
security_events

journals
journal_profiles
journal_style_maps

articles
jobs
source_files

article_model_versions

agent_runs
swarm_runs
agent_decisions
patches

validation_runs
validation_errors

review_items
review_decisions

output_files

release_runs
conversion_manifests
```

O Codex deve revisar normalização e necessidade real dessas entidades. Tokens e segredos nunca devem ser armazenados em texto puro. Tabelas de domínio devem carregar o escopo da empresa, e índices/constraints devem ajudar a impedir referências cruzadas entre empresas.

---

# FASE 24 — Reproducibilidade

Criar `ConversionManifest`.

Registrar:

```text
input IDML SHA256
input PDF SHA256
asset hashes

application git commit

OpenClaw version
Swarm configuration

OpenAI model IDs

Skill versions/hashes
prompt versions/hashes

SPS version
JATS version
Packtools version
XPM version

Article Model version

output XML SHA256
package SHA256
```

Objetivo:

Ser possível reproduzir e auditar uma conversão.

---

# FASE 25 — Observabilidade

Cada job deve ter timeline.

Exemplo:

```text
12:02 upload
12:02 parser started
12:03 parser completed
12:03 semantic swarm
12:04 metadata completed
12:05 references completed
12:05 XML build #1
12:05 Packtools: 7 errors
12:06 deterministic repair
12:06 repair swarm
12:07 XML build #2
12:07 Packtools PASS
12:08 QA PASS
12:08 XPM PASS
12:08 READY
```

Registrar também:

- modelos;
- tokens;
- custo;
- latência;
- retries;
- timeout;
- erros;
- worker;
- OpenClaw session/run ID.

---

# FASE 26 — Testes

## Unit tests

- ZIP/IDML parser;
- reading order;
- styles;
- Canonical Model;
- builders;
- ID registry;
- cross references;
- validation;
- patches;
- rule engine.

## Golden tests

```text
Canonical Article Model
       ↓
XML esperado byte-for-byte
```

quando aplicável.

## Integration

```text
IDML → Canonical Model
Canonical Model → XML
XML → Packtools
Package → XPM
```

## Swarm

Testar:

- structured output válido;
- saída inválida;
- worker timeout;
- worker crash;
- retry;
- partial failure;
- supervisor restart;
- duplicate event;
- queue recovery.

## Fault injection

Simular:

- OpenAI unavailable;
- OpenClaw unavailable;
- Redis restart;
- PostgreSQL restart;
- disk full;
- worker killed;
- XPM unavailable;
- rede interrompida.

## Identidade e autorização

Testar:

- login válido e inválido;
- rate limiting e proteção contra enumeração;
- expiração, rotação e revogação de sessão;
- recuperação de senha e tokens de uso único;
- convite, aceite e expiração;
- MFA e códigos de recuperação;
- alteração e remoção de papéis;
- usuário desativado;
- tentativa de elevação de privilégio;
- acesso horizontal a recurso de outra empresa;
- acesso vertical a operação sem permissão;
- isolamento de arquivos e object storage;
- auditoria de eventos sensíveis.

---

# FASE 27 — Corpus de homologação

Construir um corpus representativo.

Idealmente cada caso deve possuir:

```text
IDML original
PDF final
XML SciELO aprovado
assets
```

Casos mínimos:

- artigo simples;
- multilíngue;
- muitos autores;
- muitas afiliações;
- referências numerosas;
- figuras;
- tabelas complexas;
- equações;
- suplementos;
- notas;
- editorial;
- review;
- artigos com layouts diferentes;
- documentos propositalmente problemáticos.

---

# FASE 28 — Métricas de qualidade

Medir:

- Text Fidelity
- Metadata Accuracy
- Author Accuracy
- Affiliation Accuracy
- Reference Accuracy
- Figure Accuracy
- Table Accuracy
- CrossRef Accuracy
- Validation Pass Rate
- Human Review Rate
- Failure Rate
- Average Repair Passes
- Average Cost per Article
- Processing Time

Métrica principal de automação:

```text
Straight Through Processing Rate
```

Percentual de artigos que chegam a `READY_FOR_SCIELO` sem intervenção humana.

---

# FASE 29 — Aprendizado por periódico

Correções humanas devem ser armazenadas como evidência.

Não transformar automaticamente qualquer correção em regra.

Criar processo de promoção:

```text
observação recorrente
      ↓
candidate journal rule
      ↓
validação
      ↓
regra determinística
```

Objetivo:

Com o tempo, reduzir o uso da IA em periódicos com templates consistentes.

---

# FASE 30 — Segurança

A segurança deve ser tratada como requisito de arquitetura, não como acabamento.

---

# 9. Observações obrigatórias de segurança

## 9.1 IDML é um ZIP não confiável

Proteger contra:

- ZIP bombs;
- arquivos gigantes;
- milhões de entradas;
- nested archives;
- path traversal;
- caminhos absolutos;
- `../`;
- symlinks;
- hardlinks;
- nomes malformados;
- consumo excessivo de CPU/RAM/disk.

Aplicar:

- limite de upload;
- limite de arquivo individual;
- limite total descompactado;
- limite de quantidade de arquivos;
- timeout;
- extração para diretório isolado;
- normalização de paths.

Nunca extrair diretamente em diretórios da aplicação.

---

## 9.2 XML deve ser tratado como não confiável

Desativar:

- external entities;
- network access;
- DTD externo arbitrário;
- XXE;
- entity expansion não controlada.

Usar parser seguro.

Apenas DTDs/Schemas explicitamente permitidos devem ser utilizados.

---

## 9.3 Prompt injection

Conteúdo do artigo é dado não confiável.

Um texto no IDML/PDF como:

```text
Ignore suas instruções anteriores...
```

não pode afetar o agente.

Separar claramente:

- system/developer instructions;
- tool results;
- source article content.

Nunca permitir que conteúdo do artigo:

- altere tool policy;
- habilite shell;
- selecione credenciais;
- escolha endpoints;
- modifique configuração;
- crie agentes;
- altere prompts de sistema.

---

## 9.4 Princípio de menor privilégio para agentes

Agentes devem receber apenas ferramentas específicas.

Por padrão, NÃO conceder:

- shell;
- SSH;
- Docker;
- filesystem global;
- SQL livre;
- acesso a secrets;
- acesso a arquivos de outros jobs;
- acesso ao host.

Preferir ferramentas como:

```text
get_reference(id)
propose_reference_patch(...)
get_validation_error(id)
```

em vez de:

```text
read_file(path)
exec(command)
```

---

## 9.5 Isolamento entre jobs

Um artigo não pode acessar arquivos de outro artigo.

Usar:

- job IDs;
- namespaces;
- diretórios isolados;
- permissões;
- object storage prefixes;
- ACL;
- tokens temporários, se necessário.

O isolamento também deve existir entre empresas. Toda consulta, operação e chave de storage deve ser limitada pela organização obtida da sessão autenticada, nunca por um `organization_id` confiado diretamente ao cliente.

---

## 9.6 OpenClaw não deve ficar exposto publicamente

Preferir:

```text
localhost
```

ou:

```text
private Docker network
```

entre backend e OpenClaw.

Se uma API precisar existir:

- autenticação forte;
- allowlist;
- TLS;
- rate limiting;
- sem endpoints administrativos expostos.

---

## 9.7 Secrets

Nunca:

- commitar `.env`;
- colocar API keys em logs;
- passar secrets no prompt do modelo;
- salvar credenciais em resultados de agente.

Usar secret management adequado.

Rotação de credenciais deve ser possível.

---

## 9.8 Upload de assets

Validar:

- extensão;
- MIME real;
- tamanho;
- conteúdo;
- nomes;
- duplicidade.

Não confiar apenas na extensão.

---

## 9.9 Dependências e supply chain

Fixar versões críticas.

Registrar:

- Python packages;
- npm packages;
- OpenClaw;
- Packtools;
- XPM;
- containers base.

Usar lockfiles.

Realizar scanning de vulnerabilidades.

Evitar instalar pacotes automaticamente a partir de conteúdo enviado pelo usuário.

---

## 9.10 Sandbox

Processos de parsing e conversão devem ser isolados quando possível.

Considerar:

- container por worker;
- usuário não-root;
- filesystem read-only quando aplicável;
- limites de CPU/RAM;
- `no-new-privileges`;
- seccomp/AppArmor conforme ambiente permitir.

---

## 9.11 Timeouts e limites

Todos os passos externos devem possuir:

- timeout;
- retry controlado;
- limite de tentativas;
- circuit breaker quando adequado.

Incluindo:

- OpenAI;
- OpenClaw agents;
- Swarm;
- Packtools;
- XPM;
- jobs.

Nenhum loop infinito.

---

## 9.12 Auditoria

Registrar:

- quem alterou;
- o que alterou;
- origem;
- versão anterior;
- versão nova;
- motivo;
- agente/modelo;
- revisão humana.

Não registrar raciocínio privado do modelo.

Registrar apenas decisões/resultados necessários para auditoria.

---

## 9.13 Dados pessoais

Artigos podem conter:

- nomes;
- e-mails;
- ORCID;
- afiliações;
- dados ainda não publicados.

Tratar arquivos como conteúdo potencialmente confidencial.

Avaliar:

- política de retenção;
- exclusão;
- backups;
- acesso;
- logs;
- LGPD;
- termos de uso;
- acesso administrativo.

Dados de conta e eventos de autenticação também estão sujeitos a essas políticas. Definir processo para exportação, correção, desativação e exclusão quando legalmente aplicável, preservando apenas o histórico de auditoria que possua fundamento de retenção.

---

## 9.14 Backups

Backup de:

- PostgreSQL;
- source files;
- Canonical Models;
- XML;
- packages;
- Journal Profiles;
- Skills;
- plugins;
- configurações OpenClaw.

Backup só é confiável se restore for testado.

---

## 9.15 Não executar código proveniente do IDML

Nenhum script, macro, link ou conteúdo embutido deve ser executado.

---

## 9.16 Segurança de autenticação e autorização

Aplicar:

- cookies de sessão `Secure`, `HttpOnly` e `SameSite` apropriado, quando usados;
- proteção CSRF para autenticação baseada em cookies;
- CORS restrito;
- rotação de sessão após login, MFA e mudança de privilégio;
- revogação de sessões após troca de senha ou incidente;
- hashes de senha com Argon2id ou alternativa moderna equivalente;
- mensagens de erro que não permitam enumerar contas;
- logs sem senhas, tokens, cookies ou códigos MFA;
- autorização em cada operação do backend;
- auditoria de ações administrativas;
- revisão periódica de acessos e permissões.

Não usar JWT de longa duração sem estratégia de revogação. Se tokens forem necessários para APIs, utilizar curta duração, audience/scope explícitos e rotação segura de credenciais.

---

# 10. OpenClaw + Swarm: desenho desejado

## Supervisor

Responsabilidades:

- receber job;
- compreender estado;
- criar plano;
- disparar workers;
- coletar resultados;
- decidir nova etapa;
- nunca manipular XML diretamente.

## Workers

Especializados:

- metadata;
- contributors;
- affiliations;
- structure;
- references;
- figures;
- tables;
- math;
- notes.

Workers devem ser leaf nodes.

## Judges / Auditors

- Fidelity Auditor
- Metadata Auditor
- Reference Auditor
- CrossRef Auditor
- Structure Auditor
- Asset Auditor
- Release Judge

## Swarms principais

### Semantic Extraction Swarm

Interpretação paralela.

### Reference Swarm

Processamento de bibliografia em chunks.

### QA Swarm

Auditoria adversarial.

### Repair Swarm

Correção apenas de problemas semânticos.

### Release Swarm

Gate final lógico, sem editar dados.

---

# 11. Uso adaptativo de modelos

O Codex deve propor estratégia de modelos.

Sugestão:

## Workers

Modelo mais rápido/econômico para:

- classificação;
- extração;
- referências simples;
- operações estruturadas.

## Specialists

Modelo mais forte para:

- afiliações complexas;
- referências ambíguas;
- estrutura difícil;
- tabelas incomuns;
- conflitos de fontes.

## Judge

Modelo de maior capacidade para:

- adjudicação;
- QA;
- release.

Toda escolha deve ser configurável.

Não hardcodar um único modelo.

---

# 12. Confiança e Human Review

Cada decisão semanticamente incerta deve ter:

- confidence;
- evidence;
- reason;
- alternatives.

Não assumir que a confiança declarada pelo LLM é uma probabilidade calibrada.

O Codex deve propor um `ReviewScore` combinando:

- agreement entre agentes;
- evidência estrutural;
- style mapping;
- validadores;
- consistência com PDF;
- histórico do periódico;
- indicadores do modelo.

Itens abaixo de limiar devem ir para revisão.

---

# 13. PDF como segunda fonte

IDML:

- verdade estrutural/diagramática.

PDF:

- verdade visual/editorial final.

O sistema deve evitar OCR quando o PDF possuir camada textual utilizável.

Comparar:

- conteúdo;
- ordem;
- títulos;
- autores;
- figuras;
- tabelas;
- referências;
- legendas.

---

# 14. Repair pipeline

O sistema deve classificar erros antes de chamar IA.

Exemplos:

## Determinístico

```text
duplicate ID
```

Resolver por código.

## Semântico

```text
autor pode estar associado a duas afiliações possíveis
```

Enviar a agente.

## Missing Data

```text
data de aceite não existe nas fontes
```

Solicitar revisão humana.

---

# 15. Critérios para READY_FOR_SCIELO

O Codex deve validar com a documentação vigente e ajustar esta lista.

Conceitualmente:

```text
✓ IDML parsed

✓ Canonical Article Model valid

✓ mandatory metadata satisfied

✓ textual fidelity

✓ authors resolved

✓ affiliations resolved

✓ references resolved

✓ figures resolved

✓ tables resolved

✓ equations resolved

✓ cross-references resolved

✓ assets present

✓ XML well formed

✓ JATS/DTD valid

✓ SPS valid

✓ Packtools valid

✓ internal rules valid

✓ QA approved

✓ Release approved

✓ XPM approved, se aplicável/obrigatório
```

Qualquer bloqueador:

```text
NEEDS_REVIEW
```

ou:

```text
FAILED
```

---

# 16. Critério de sucesso da primeira versão

A V1 não precisa converter qualquer IDML existente no mundo.

Estratégia:

## Piloto 1

- um periódico;
- um template IDML;
- corpus conhecido.

## Piloto 2

- 2–3 periódicos;
- templates diferentes.

## Piloto 3

- layouts variados.

Somente depois tentar:

```text
generic IDML
```

Objetivo da V1:

> Demonstrar um pipeline completo, reproduzível e seguro de IDML → XML SciELO validado para um conjunto controlado de documentos reais.

---

# 17. O que NÃO fazer

O Codex não deve simplificar o projeto das seguintes formas sem justificar e obter aprovação:

## Não remover o Canonical Article Model

Evitar:

```text
IDML → LLM → XML
```

## Não deixar agentes editar XML diretamente

## Não usar LLM para regras formalmente determinísticas

## Não expor shell desnecessariamente aos agentes

## Não armazenar apenas o estado final

## Não sobrescrever decisões sem histórico

## Não hardcodar SPS `latest`

## Não considerar validação do LLM equivalente a Packtools/XPM

## Não assumir ordem de leitura do IDML pela ordem dos arquivos ZIP

## Não assumir que confidence do LLM é probabilidade calibrada

## Não atualizar OpenClaw antes do baseline/backup

## Não desenvolver diretamente em produção

---

# 18. Entregáveis que o Codex deve devolver após a análise inicial

Antes de iniciar a implementação completa, produzir:

## 18.1 `ARCHITECTURE_REVIEW.md`

Contendo:

- pontos aprovados;
- pontos questionados;
- alternativas;
- simplificações seguras;
- riscos;
- dependências;
- decisões recomendadas.

---

## 18.2 `ENVIRONMENT_BASELINE.md`

Ambiente HostGator/Linux/OpenClaw.

---

## 18.3 `SCIELO_REQUIREMENTS.md`

Requisitos oficiais atuais.

---

## 18.4 `XPM_FEASIBILITY.md`

Viabilidade XPM/Linux.

---

## 18.5 `IDML_MODEL_ANALYSIS.md`

Análise estrutural do formato e dos arquivos reais.

---

## 18.6 `CANONICAL_ARTICLE_MODEL.md`

Modelo proposto.

---

## 18.7 `OPENCLAW_SWARM_DESIGN.md`

Arquitetura real baseada na versão instalada do OpenClaw.

---

## 18.8 `OPENCLAW_TOOL_CONTRACTS.md`

Ferramentas tipadas.

---

## 18.9 `AGENT_OUTPUT_SCHEMAS.md`

JSON Schemas.

---

## 18.10 `SECURITY_MODEL.md`

Threat model e controles.

---

## 18.11 `TEST_STRATEGY.md`

Plano de testes.

---

## 18.12 `IMPLEMENTATION_BACKLOG.md`

Backlog por fases.

Cada item deve informar:

- dependências;
- criticidade;
- paralelização possível;
- critérios de aceite;
- riscos.

Não é necessário estimar tempo, salvo se houver necessidade operacional específica.

---

## 18.13 `IDENTITY_AND_ACCESS_MODEL.md`

Contendo:

- empresas e memberships;
- fluxos de autenticação;
- matriz de papéis e permissões;
- modelo de sessões e MFA;
- isolamento multiempresa;
- contas de serviço;
- auditoria de segurança;
- critérios de aceite e testes de autorização.

---

# 19. Perguntas que o Codex deve responder explicitamente

1. A arquitetura proposta é adequada para produção?
2. Quais partes estão excessivamente complexas?
3. Quais partes estão insuficientemente especificadas?
4. Existe alternativa tecnicamente superior ao Canonical Article Model?
5. Existe alternativa melhor para parser IDML?
6. Como preservar reading order em IDML de maneira confiável?
7. Qual versão SPS deve ser implementada primeiro?
8. Como versionar SPS/JATS?
9. Packtools funciona adequadamente no stack proposto?
10. XPM pode ser automatizado confiavelmente em Linux?
11. Se não, qual arquitetura de XPM worker deve ser usada?
12. A versão atual do OpenClaw suporta integralmente o desenho Swarm?
13. Quais APIs do Swarm são experimentais e podem mudar?
14. Como encapsular essas APIs?
15. Qual fallback utilizar se Swarm falhar?
16. Quais ferramentas cada agente deve receber?
17. Como impedir prompt injection através do artigo?
18. Como garantir isolamento entre jobs?
19. Como lidar com ZIP bomb/XXE/path traversal?
20. Como tratar PDFs de forma segura?
21. Qual estratégia de storage utilizar?
22. Celery/Redis é apropriado ou existe alternativa melhor?
23. Como retomar jobs após restart?
24. Como garantir idempotência?
25. Como versionar e auditar patches?
26. Como estruturar o Release Gate?
27. Como medir fidelidade entre IDML/PDF/XML?
28. Como construir corpus de gold standard?
29. Quais métricas definem qualidade suficiente?
30. Quais são os principais motivos técnicos para um artigo exigir revisão humana?
31. Quais decisões podem ser determinísticas e quais realmente precisam de IA?
32. Como minimizar custo de tokens/modelos?
33. Como testar agentes de forma reproduzível?
34. Como testar alterações de OpenClaw/Swarm sem comprometer produção?
35. Qual estratégia de backup e restore é adequada?
36. Quais riscos não contemplados neste documento o Codex identifica?
37. A autenticação será local ou delegada a um provedor OIDC?
38. Um usuário poderá pertencer a quantas empresas e periódicos?
39. Qual matriz de papéis e permissões atende ao fluxo editorial real?
40. Quais ações exigem MFA, reautenticação ou dupla aprovação?
41. Como garantir isolamento multiempresa no banco, filas, cache, logs e storage?
42. Qual política de sessão, convite, recuperação, bloqueio e desativação será usada?

---

# 20. Ordem recomendada após aprovação da análise

```text
A. Baseline da infraestrutura
B. Validação SciELO / Packtools / XPM
C. Canonical Article Model
D. Parser IDML
E. SPS/JATS Builder
F. Primeiro XML válido sem IA
G. Journal Profiles
H. OpenClaw tools
I. Skills
J. Semantic Swarm
K. Reference Swarm
L. PDF Fidelity
M. QA Swarm
N. Validation/Classification
O. Repair Swarm
P. Human Review
Q. Web UI completa
R. Release Swarm
S. Package/XPM Gate
T. Corpus e testes
U. Piloto controlado
V. Produção
```

---

# 21. Instrução final ao Codex

## Primeira tarefa

**NÃO comece escrevendo o sistema completo.**

Primeiro:

1. inspecione o ambiente;
2. consulte a documentação oficial vigente;
3. valide as premissas;
4. identifique incompatibilidades;
5. faça os spikes necessários;
6. proponha alterações;
7. produza os documentos de análise listados;
8. apresente um backlog técnico revisado.

## Critério para começar implementação

O projeto somente deve entrar em desenvolvimento completo após existir confiança suficiente em quatro pontos:

```text
1. Estrutura e reading order de IDML
2. Canonical Article Model
3. Validação SPS/Packtools/XPM
4. Integração segura e sustentável com OpenClaw Swarm
```

## Restrição arquitetural importante

> Não simplificar o projeto substituindo o pipeline por um prompt que converta IDML diretamente em XML.

O objetivo não é criar uma demonstração que funciona em alguns artigos.

O objetivo é criar uma plataforma:

- confiável;
- auditável;
- reproduzível;
- segura;
- escalável;
- capaz de melhorar por periódico;
- capaz de detectar as próprias incertezas;
- e capaz de produzir XML SciELO com intervenção humana somente quando existir ambiguidade real.

---

# 22. Resultado esperado da análise do Codex

Ao final da análise, esperamos receber uma conclusão semelhante a:

```text
ARCHITECTURE STATUS:
APPROVED / APPROVED WITH CHANGES / REQUIRES REDESIGN

CRITICAL RISKS:
...

XPM:
...

OPENCLAW/SWARM:
...

IDML:
...

CANONICAL MODEL:
...

SECURITY:
...

RECOMMENDED CHANGES:
...

GO/NO-GO FOR IMPLEMENTATION:
...
```

Somente após esse parecer deve começar a implementação por fases.

---

# 23. Filosofia final do sistema

```text
OpenClaw / Swarm
    interpreta
    coordena
    compara
    audita
    decide

Python / SciELO Engine
    extrai
    estrutura
    aplica patches
    gera XML
    valida
    empacota

SciELO validators
    determinam conformidade
```

Em uma frase:

> **OpenClaw coordena a inteligência; o SciELO Engine mantém a verdade estrutural; os validadores oficiais determinam se o resultado está apto para publicação.**
