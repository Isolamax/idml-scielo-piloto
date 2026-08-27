# Política de custo monetário dos agentes

Data: 2026-08-27. Versão do catálogo: `agent-pricing-1.0`.

## Regra operacional

Cada resposta de provedor deve ter seu custo resolvido antes de ser aceita como proposta:

1. custo em micro-USD informado pelo provedor é a fonte prioritária (`provider`);
2. sem custo informado, a aplicação aceita somente estimativa calculada por uma tarifa exata de
   `provider/model` no catálogo versionado (`estimated`);
3. sem uma dessas fontes, a execução termina em `COST_UNAVAILABLE`, sem aceitar o payload do
   agente (`unavailable`).

O cálculo usa tokens de entrada e saída separadamente, tarifas em USD por milhão de tokens e
arredondamento para cima até o micro-USD. O teto `max_cost_microusd` é aplicado ao custo resolvido.
Tokens, provider, modelo, fonte do custo, versão do catálogo e chave tarifária são preservados no
`AgentRun` append-only, inclusive quando o teto bloqueia a proposta.

O teto avaliado após a resposta impede que uma proposta acima do orçamento entre no fluxo
editorial. Ele não evita o consumo já ocorrido na chamada. Bloqueio pré-chamada somente será
permitido futuramente quando o modelo efetivo e todos os componentes tarifáveis forem conhecidos
antes da execução.

## Catálogo de produção

O arquivo `config/agent-pricing-v1.json` é a fonte versionada. Chaves devem ser exatas e
normalizadas no formato `provider/model`; não há fallback por família, alias ou aproximação.
Cada tarifa exige fonte e data de vigência.

O alias observado no OpenClaw é `openai/gpt-5.4-mini`. Em 2026-08-27, o caminho do gateway não
expôs custo monetário e não foi possível verificar uma tarifa oficial exata para esse alias. Por
isso, ele consta como não precificado e a lista `models` permanece vazia. Nenhum preço aproximado
foi inventado.

Enquanto o provider não retornar custo ou uma tarifa oficial exata não for validada e registrada:

- `IDML_FEATURE_OPENCLAW=false`;
- `IDML_FEATURE_AI_SWARM=false`;
- qualquer resposta sem custo falha fechada;
- o Gate G6 continua bloqueado.

## Alteração de tarifa

Uma alteração exige nova versão do catálogo, fonte oficial verificável, data de vigência, testes
de cálculo/limite, revisão do teto por artigo e implantação com flags desligadas. Registros antigos
mantêm `pricing_version` e `pricing_model_key`, portanto não são reinterpretados por preços novos.
