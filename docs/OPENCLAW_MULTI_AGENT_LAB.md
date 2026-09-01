# Laboratório multiagente OpenClaw

## Objetivo

O laboratório mede a qualidade de propostas XML antes da homologação humana final. Ele não altera
artigos, não persiste propostas na aplicação e não autoriza release. Toda conclusão permanece
provisória com `needs_human=true` até o Gate Humano Final G8-H.

## Papéis e isolamento

Cada caso usa quatro sessões OpenClaw distintas, sem ferramentas ou Skills:

1. `proposer`: produz uma proposta estruturada a partir da evidência autorizada;
2. `xml_critic`: verifica contrato, evidência, paths e integridade XML/JATS;
3. `editorial_critic`: verifica fidelidade semântica, omissão, invenção e normalização;
4. `adjudicator`: consolida apenas as saídas estruturadas anteriores.

O alvo automático (`expected_value`) nunca é enviado aos agentes. Raciocínio privado não é
compartilhado entre sessões; críticos recebem somente o caso minimizado e a proposta, e o
adjudicador recebe somente proposta e críticas. Prompts e schemas são versionados e incluídos por
hash no manifesto.

## Precedência determinística

O juiz local valida novamente hashes, paths, atomicidade de `RichText`, escopo, política, injeção e
vínculos entre as quatro saídas. Concordância dos agentes não substitui evidência. Se houver consenso
positivo sem ganho sobre o baseline automático, o resultado final é `abstained` com risco de falso
consenso. Erro operacional encerra a janela; violação de contrato rejeita o caso.

## Janela v1

A configuração `config/openclaw-multi-agent-lab-v1.json` seleciona inicialmente os casos ESA de
metadados e referências. São oito chamadas sequenciais, tentativa única, timeout de 45 segundos por
papel e teto agregado de 150.000 micro-USD (US$ 0,15). As flags
`IDML_FEATURE_OPENCLAW` e `IDML_FEATURE_AI_SWARM` devem permanecer falsas.

O dataset e o manifesto ficam privados em `benchmarks/private/input`; resultados brutos e relatório
sanitizado ficam em `benchmarks/private/output`, todos em modo 600. O relatório público contém apenas
métricas, códigos de decisão, hashes e custo — nunca trechos, valores propostos ou respostas brutas.

## Operação na VPS

Preparar e validar o manifesto, sem inferência:

```sh
cd /opt/idml-platform
./ops/openclaw-multi-agent-lab.sh prepare multi-agent-first-window
```

Executar somente em janela autorizada:

```sh
cd /opt/idml-platform
IDML_CONFIRM_AGENT_EXECUTION=RUN_IDML_OPENCLAW_MULTI_AGENT_LAB_V1 \
  ./ops/openclaw-multi-agent-lab.sh execute multi-agent-first-window
```

O script verifica zero `agent_runs`/`agent_proposals`, faz backup e restore test, ativa o provider
somente durante a janela e sempre chama o kill switch no encerramento. O pós-teste deve confirmar
flags falsas, zero sessões, ausência do proxy/redes transitórias e saúde da aplicação, do gateway
dedicado e do OpenClaw compartilhado.

## Critério para ampliar o corpus

A primeira janela valida o mecanismo, não o Gate G6-T. A expansão exige casos positivos, negativos,
ambíguos, de abstenção e injeção para cada domínio; toda falha confirmada vira fixture. O G6-T só pode
ser aprovado após cobertura integral, metas técnicas satisfeitas e relatório por domínio, sem
antecipar a homologação do especialista em XML.

## Evidência da primeira janela

Em 2026-09-01, `multi-agent-first-window-v1` concluiu os dois casos por 32.824 micro-USD. Metadados
foi exato e aceito somente para futura revisão humana. Referências foi rejeitado pelo juiz local antes
dos críticos porque as duas representações atômicas de `RichText` divergiram. O caso foi convertido
em teste de regressão. O relatório sanitizado está em
`benchmarks/agents/reports/multi-agent-first-window-v1.json`; o resultado bruto permanece privado.
