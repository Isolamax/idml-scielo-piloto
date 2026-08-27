# Integração da aplicação com o gateway OpenClaw

Data: 2026-08-27. Estado: implementada e desativada.

## Contrato escolhido

A aplicação usa o endpoint OpenResponses `POST /v1/responses`, nunca CLI interativo ou acesso ao
workspace. O cliente `OpenClawResponsesClient`:

- fixa o agente com `x-openclaw-agent-id`;
- fixa o backend `openai/gpt-5.4-mini` com `x-openclaw-model`;
- usa chave de sessão tenant-bound;
- envia envelope canônico minimizado e schema fechado;
- não segue redirects e aceita somente JSON até 2 MiB;
- exige exatamente uma saída textual contendo um objeto JSON;
- rejeita ausência/invalidade de usage, token negativo e cache maior que a entrada;
- não registra token do gateway nem conteúdo bruto em mensagens de erro.

O gateway não recebe ferramentas nativas. As leituras tenant-bound já foram realizadas pelo
backend e estão no envelope; a proposta retornada continua passando pelo schema e pelos validadores
determinísticos da aplicação.

## Uso e custo

O OpenClaw normaliza contadores OpenAI em `usage.input_tokens`, `usage.output_tokens` e
`usage.input_tokens_details.cached_tokens` quando o provider entrega esses dados. A aplicação
persiste os três contadores e calcula o custo pelo catálogo próprio, sem depender da estimativa
visual do OpenClaw.

O modelo foi fixado no registro `agent-config-1.2`. A tarifa oficial verificada está em
`agent-pricing-1.1`: US$ 0,75/M entrada, US$ 0,075/M entrada em cache e US$ 4,50/M saída. Com os
limites iniciais de 12 mil tokens de entrada e 2 mil de saída, o preflight conservador é de
18.000 micro-USD (US$ 0,018), abaixo do teto por artigo de 50.000 micro-USD (US$ 0,05).

O preflight ocorre antes da chamada e assume zero cache. O serviço bloqueia novos runs quando a
soma append-only do artigo consumiu o teto; a linha do recurso é bloqueada na transação para evitar
duas reservas concorrentes. Custos reais de runs falhos também entram na soma quando conhecidos.

## Fronteira de segurança da VPS

O endpoint OpenResponses está desativado no OpenClaw atual. Segundo o contrato do gateway, segredo
compartilhado restaura o conjunto completo de escopos de operador, mesmo quando o cliente pede
escopos menores. Conectar a aplicação ao OpenClaw compartilhado do Mapalead ampliaria
desnecessariamente o impacto de um comprometimento.

Antes de habilitar `IDML_FEATURE_OPENCLAW`, escolher e validar uma destas opções:

1. instância OpenClaw dedicada ao IDML, com rede Docker exclusiva, agente único, ferramentas/skills
   vazios, limites de CPU/RAM e segredo próprio; opção recomendada;
2. autenticação identity-aware com escopos mínimos efetivamente honrados pelo gateway, depois de
   teste negativo documentado.

Até essa fronteira existir, não configurar o token na aplicação, não conectar redes Docker e manter
as duas flags de IA falsas. O OpenClaw e o Mapalead atuais não devem ser reiniciados ou alterados
por este incremento.
