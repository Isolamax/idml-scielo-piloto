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

## Janela v2 — corpus ESA disponível

A configuração `config/openclaw-multi-agent-lab-v2.json` seleciona os dez casos reais disponíveis:
metadados, autores/afiliações, referências e figuras/tabelas. São no máximo 40 chamadas sequenciais,
tentativa única, timeout de 45 segundos por papel e teto agregado de 585.000 micro-USD. O contrato
atômico de `RichText` fornece template completo, exige inlines não vazios, preserva todos os campos e
IDs e permite alterar somente o texto, cuja concatenação deve reproduzir exatamente o valor plain.

O endpoint OpenResponses da versão OpenClaw fixada não aceita o campo `text.format` do Responses API.
Por isso o cliente mantém o schema nas instruções, aceita JSON puro ou um único fence Markdown que
contenha somente JSON e rejeita qualquer texto externo. Falha de contrato rejeita apenas o caso e
reserva o custo máximo do papel; falha operacional ou de política encerra a janela inteira.

O dataset e o manifesto ficam privados em `benchmarks/private/input`; resultados brutos e relatório
sanitizado ficam em `benchmarks/private/output`, todos em modo 600. O relatório público contém apenas
métricas, códigos de decisão, hashes e custo — nunca trechos, valores propostos ou respostas brutas.

## Janela v3 — evidência completa segmentada

A configuração `config/openclaw-multi-agent-lab-v3.json` usa os mesmos dez casos reais com o dataset
privado v1.4. Cada evidência é dividida em segmentos de até 500 caracteres, limitada a 16 segmentos
e 8.000 caracteres. Cada segmento tem hash próprio; o hash agregado vincula identidade, locator,
ordem, contagem, tamanho e todos os hashes. A remontagem é sem separadores e deve reproduzir o texto
integral. Ausência, reordenação, alteração, mistura com o formato legado ou estouro do limite falha
antes de qualquer chamada ao agente.

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

Preparar ou executar a janela v2 requer o terceiro argumento e a confirmação própria:

```sh
cd /opt/idml-platform
./ops/openclaw-multi-agent-lab.sh prepare multi-agent-full-corpus v2
IDML_CONFIRM_AGENT_EXECUTION=RUN_IDML_OPENCLAW_MULTI_AGENT_LAB_V2 \
  ./ops/openclaw-multi-agent-lab.sh execute multi-agent-full-corpus v2
```

A janela v3 usa dataset v1.4 e confirmação distinta:

```sh
cd /opt/idml-platform
./ops/openclaw-multi-agent-lab.sh prepare multi-agent-segmented-corpus v3
IDML_CONFIRM_AGENT_EXECUTION=RUN_IDML_OPENCLAW_MULTI_AGENT_LAB_V3 \
  ./ops/openclaw-multi-agent-lab.sh execute multi-agent-segmented-corpus v3
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

## Evidência da janela v2

Em 2026-09-01, `multi-agent-full-corpus-v2r2` concluiu os dez casos e 26 chamadas por 218.200
micro-USD. Metadados passou nas sete verificações determinísticas, foi exato contra o alvo automático
e ficou aceito somente para a futura revisão humana. Os nove casos restantes foram rejeitados por
`AGENT_OUTPUT_NOT_JSON`: duas falhas no proponente, quatro no crítico XML e três no adjudicador. A
aceitação do fence JSON exato não alterou a taxa da janela anterior, portanto saída estruturada
confiável continua uma pendência técnica do gateway/modelo, e não deve ser contornada extraindo JSON
de prosa arbitrária.

O custo conservador acumulado das janelas deste artigo ficou em 528.995 micro-USD. O relatório
público sanitizado está em `benchmarks/agents/reports/multi-agent-full-corpus-v2.json`; resultados
brutos permanecem privados em modo 600. O pós-teste confirmou flags falsas, zero
runs/propostas/sessões, ausência de chave do provider no gateway, proxy e redes transitórias
ausentes, API/interface em HTTP 200 e os dois OpenClaw saudáveis sem reinicialização do compartilhado.
O token do gateway dedicado foi rotacionado após a auditoria, sem registrar o valor anterior ou o
novo. O G6-T continua pendente.

## Matriz adversarial local v1

O arquivo `benchmarks/agents/adversarial-matrix-v1.json` congela cinco cenários para cada um dos seis
domínios: positivo, negativo por valor inventado, evidência ambígua, falso consenso que exige
abstenção e prompt injection. Estrutura e matemática usam dados estritamente sintéticos; essa
cobertura prova contratos, mas não substitui casos reais autorizados nem baseline humano.

Executar sem chave, rede ou provider:

```sh
python -m idml_foundation.ai.adversarial_matrix \
  --matrix benchmarks/agents/adversarial-matrix-v1.json \
  --report-output tmp/adversarial-matrix-v1-report.json
```

A execução determinística de 2026-09-01 passou os 30 casos e 84 chamadas simuladas, com zero chamada
de provider e custo monetário zero. Foram seis aceitações somente para revisão humana, doze rejeições
e doze abstenções. Seis consensos positivos sem ganho foram bloqueados; os seis ataques de prompt
injection e os seis valores inventados com metadados de evidência válidos foram rejeitados antes dos críticos. Nenhuma
ferramenta ou Skill foi exposta. O relatório público sanitizado é
`benchmarks/agents/reports/adversarial-matrix-v1-report.json`.

A mesma matriz foi reproduzida na VPS dentro da imagem fixada do runner, em contêiner read-only,
usuário não root, capabilities removidas e `--network none`. O resultado permaneceu 30/30, 84 papéis,
zero provider e custo zero, sem recriar ou reiniciar os serviços da aplicação.

## Sustentação evidencial determinística

Toda proposta passa agora por `normalized_exact` antes dos críticos. O valor proposto deve coincidir
integralmente com o trecho autorizado após apenas normalização Unicode NFKC, espaços e
deshifenização de quebra de linha. Maiúsculas, conteúdo adicional, reescrita semântica e valores não
textuais não são aceitos. A regra não consulta o alvo oculto e não pode ser anulada por consenso.

O dataset ESA v1.4 removeu truncamento sem ampliar o texto por inferência. Os dez alvos automáticos
têm sustentação integral: são 12 segmentos em dez casos, duas referências usam múltiplos segmentos
e o maior valor tem 734 caracteres. Hashes individuais, hash agregado e remontagem passaram; nenhum
trecho aparece no relatório público. O histórico de 8/10 permanece em
`benchmarks/agents/reports/grounding-corpus-v1-report.json`; o resultado atual está em
`benchmarks/agents/reports/grounding-corpus-v2-report.json`. Isso resolve a completude evidencial,
mas não a saída JSON real nem a ausência de casos reais de estrutura e matemática.
