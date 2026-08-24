# OpenClaw e desenho da orquestração assistiva

## Resultado da auditoria

```text
OPENCLAW_VERSION: 2026.6.11
AUDIT_MODE: READ_ONLY
NATIVE_SWARM_PRIMITIVE_CONFIRMED: NO
PIPELINE_DEPENDENCY: OPTIONAL
DEFAULT_ORCHESTRATOR: SEQUENTIAL
```

Nenhuma configuração, agente, sessão, hook, plugin, skill ou token foi alterado.

## Capacidades observadas

- gateway saudável, restrito ao loopback e autenticado por token;
- comandos de agentes, execução de agente, gateway, hooks, plugins, skills e backup;
- 10 agentes configurados e 90 sessões ativas no instante da inspeção;
- suporte a ferramentas/plugins e saída JSON em comandos aplicáveis;
- plugin `LLM Task` voltado a JSON-only presente, porém desabilitado;
- persistência em volumes Docker para configuração e workspace;
- modelos diversos configurados;
- auditoria de segurança com 0 critical, 1 warning e 2 info.

A CLI instalada não expôs um comando ou contrato formal denominado Swarm. Subagentes e coordenação podem ser construídos na camada da aplicação, mas não serão presumidos como uma API estável do OpenClaw.

## Restrições de segurança

O OpenClaw opera com modelo de confiança de assistente pessoal, não como serviço multi-tenant para conteúdo hostil. Há ferramentas elevadas/browser control disponíveis e o container executa como root. Consequentemente:

- usuários do produto nunca recebem acesso direto ao gateway;
- autorização de empresa/usuário ocorre exclusivamente no backend da aplicação;
- texto do artigo é entrada não confiável e não pode redefinir ferramentas/políticas;
- agentes não recebem segredos, acesso ao banco inteiro ou filesystem compartilhado;
- cada chamada recebe escopo mínimo, timeout, orçamento e schema de saída;
- nenhuma resposta de agente concede `READY_FOR_SCIELO`.

## Porta abstrata de orquestração

O domínio dependerá de uma interface própria, conceitualmente:

```text
run(task_type, tenant_id, job_id, input_ref, output_schema,
    idempotency_key, timeout, budget, tool_allowlist) -> OrchestrationResult
```

`OrchestrationResult` deve conter status, proposta tipada, evidências, confiança, versão do modelo, provider, timestamps, custo, tentativas e erro normalizado. O agente não recebe permissão para gravar diretamente no modelo canônico ou XML.

Implementações planejadas:

- `SequentialOrchestrator`: padrão, previsível e utilizado no início;
- `OpenClawOrchestrator`: adapter opcional e atrás de feature flag;
- provider direto alternativo, caso necessário;
- `NoOpOrchestrator`: modo degradado sem IA.

## Fluxo assistivo futuro

1. pipeline determinístico cria `ReviewItem` com evidência limitada;
2. policy verifica tenant, classificação do dado, orçamento e tarefa allowlisted;
3. orchestrator envia somente o recorte necessário;
4. saída é validada contra JSON Schema fechado;
5. proposta vira patch tipado pendente;
6. aplicação valida precondições, permissões e versão do objeto;
7. patch aceito cria nova versão do modelo;
8. validadores determinísticos executam novamente;
9. auditoria registra quem/qual agente propôs, aprovou e aplicou.

## Concorrência, timeout e retries

- concorrência inicial de IA: 1;
- timeout explícito por tarefa e cancelamento propagado;
- no máximo uma repetição automática para falha transitória; reparo semântico tem ciclo próprio e limitado;
- idempotency key obrigatória para impedir duplicação;
- circuit breaker por provider/modelo;
- sessões não são fonte de verdade do job;
- estado persistente fica no banco da aplicação, não na memória do agente.

## Casos de uso permitidos na Fase 6

- classificar bloco ambíguo com evidências;
- sugerir vínculo autor-afiliacão;
- estruturar referência com baixa confiança explícita;
- comparar divergências e recomendar revisão;
- propor patch dentro de operações allowlisted.

Casos proibidos:

- gerar XML final livremente;
- inventar metadados ausentes;
- ignorar validador;
- executar shell/browser a partir do conteúdo do artigo;
- cruzar dados entre empresas;
- aprovar release.

## Critério para habilitar OpenClaw

OpenClaw só entra no caminho de um tipo de tarefa após existir baseline determinístico, dataset de avaliação, schema fechado, testes de prompt injection, limite de custo e rollback. Desabilitar a feature flag deve manter o pipeline principal operacional.
