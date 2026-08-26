# Autoavaliação técnica do corpus inicial e da amostra ESA

Data: 2026-08-26. Estado: **evidência técnica provisória; não substitui revisão humana**.

## Escopo e proteção dos dados

A avaliação usou os seis IDMLs autorizados do corpus inicial e a amostra ESA colocada em
`C:\IDML\tmp\sample`. Conteúdo integral, valores editoriais e respostas brutas do modelo não foram
versionados. A VPS recebeu apenas sete fragmentos minimizados, em diretório privado e modo 600.
Relatórios versionáveis contêm somente hashes, contagens, métricas e códigos de falha. O artigo de
holdout foi executado uma única vez para medição final e não foi usado para ajustar prompt.

## Integridade e leitura da amostra ESA

Os dez arquivos fornecidos conferem por tamanho e SHA-256 com o manifesto `esa-e20240086`. O ZIP
da entrega, presente no manifesto, não veio nesta cópia da amostra e não foi necessário para a
inspeção. O PDF tem dez páginas, camada textual, cinco figuras visualmente coerentes e nenhuma
figura ausente ou cortada observada. Os cinco nomes de `graphic/@xlink:href` do XML correspondem
exatamente aos cinco JPEGs.

| Componente | Referência aprovada |
|---|---:|
| Stories / frames do IDML | 46 / 55 |
| Seções de primeiro nível / todas as seções | 4 / 11 |
| Parágrafos do corpo | 78 |
| Autores / afiliações | 3 / 3 |
| Figuras / tabelas | 5 / 3 |
| Fórmulas inline / display | 2 / 15 |
| Referências / notas | 52 / 4 |
| Páginas | 10 |

A planilha `falsos positivos.xlsx` possui uma única linha e registra `Nenhum` falso positivo. Isso
não significa zero erro: o relatório XPM 4.0.096 contém 0 blocking, 0 fatal, 1 error e 119 warnings.
O erro é uma referência `B37` existente na lista, mas não citada por nenhum `xref` bibliográfico.
A nova regra offline `uncited-reference` reproduz exatamente essa ocorrência como warning local;
o XPM do candidato continua sendo o gate externo bloqueador.

## Comparação determinística

O Gate G3 passou na amostra relocalizada. O Gate G4 também encontrou os assets por hash na nova
subpasta, construiu pacote byte-determinístico e obteve fidelidade aprovada:

| Componente | PDF recall | XML recall |
|---|---:|---:|
| Títulos | 1,000000 | 1,000000 |
| Autores | 1,000000 | 1,000000 |
| Corpo | 0,989725 | 0,996881 |
| Referências | 0,999454 | 1,000000 |
| Figuras e tabelas | 1,000000 | 1,000000 |

O release continua bloqueado porque SPSValidator e XPM não foram executados contra o pacote novo.
Além disso, o XML gerado contém 52 referências, mas nenhum `xref` bibliográfico. Essa é a maior
lacuna determinística descoberta pela amostra. O XML aprovado possui 51 referências citadas e uma
não citada.

A comparação textual exata contra o XML aprovado deve ser tratada como proxy técnico, não como
qualidade semântica: text fidelity foi 0,94218; autores tiveram F1 1,0; estrutura F1 0,88; as demais
comparações exatas foram penalizadas por diferenças de representação e formatação. A contagem
estrutural, o PDF e a validação devem ser considerados em conjunto.

## Generalização para os outros artigos iniciais

Os cinco documentos RBEdu foram abertos de forma segura e tiveram Stories, frames e spreads
extraídos, mas o perfil ESA não reconheceu seus estilos: autores, afiliações, seções e referências
canônicas ficaram em zero e a validação falhou. Isso confirma que o sistema é, por enquanto,
específico do template ESA. O holdout RBEdu confirmou a mesma falha de generalização e não foi
usado para mudanças posteriores.

## Benchmark OpenClaw corrigido — v1.1

A primeira rodada com dez casos revelou que três patches exatos de legendas não podiam ser
aplicados porque alteravam `plain.value` sem atualizar os `inlines`. O construtor do benchmark foi
corrigido para excluir esses caminhos escalares acoplados. A versão 1.1 contém sete casos
aplicáveis e registra oito legendas (cinco figuras e três tabelas) como cobertura pendente.

Resultado do agente dedicado `idml-evaluator` com `openai/gpt-5.4-mini`:

| Métrica | Resultado |
|---|---:|
| Casos | 7 |
| Schema e evidência válidos | 5/7 (71,43%) |
| Patch exato no contrato | 1/7 (14,29%) |
| Canônico e JATS válidos | 5/7 (71,43%) |
| Casos com melhora mensurável | 2/7 (28,57%) |
| Casos exatos e aplicáveis | 1/7 (14,29%) |
| Conformidade com orçamento de tokens | 7/7 |
| Tokens médios de entrada / saída | 8.828,43 / 454,86 |
| Latência média | 6,88 s |

Um caso de metadados retornou saída OpenClaw inválida. Um caso de referências produziu hash de
evidência fora do schema. Os três casos de afiliação conservaram o valor original, sem melhora. Um
caso de referência foi corrigido exatamente e outro melhorou apenas 0,00118 de similaridade. Entre
os cinco casos comparáveis, a similaridade média subiu de 0,68071 para 0,74210, mas o resultado é
dominado por um único acerto e não comprova ganho editorial generalizável.

## Decisão e próximos incrementos

Os resultados mantêm `IDML_FEATURE_OPENCLAW=false` e `IDML_FEATURE_AI_SWARM=false`. G6 permanece
bloqueado e a Fase 7 não deve começar. Ordem recomendada de desenvolvimento:

1. extrair e resolver citações bibliográficas no mapeamento ESA, com CrossRef Accuracy explícita;
2. definir patch atômico para `RichText`, preservando ou reconstruindo `plain` e `inlines` juntos;
3. reforçar structured output/evidence binding e reduzir o prompt de aproximadamente 9 mil tokens;
4. implementar observação de custo monetário por chamada;
5. criar profile/style mapping RBEdu somente quando a expansão de template for autorizada;
6. repetir o benchmark com corpus maior e baseline humano assim que revisores estiverem disponíveis.

## Evidência de implantação na VPS

O código e o relatório sanitizado foram implantados na imagem
`idml-foundation:phase6-corpus-v1.1`, ID
`sha256:e1d56c0de344a0210872fb55b639603dde66370418559f8f16543935a982e146`. API e
worker ficaram healthy; PostgreSQL e Redis foram preservados. A migration permanece em
`d5f6a7b8c9d0`, com zero `agent_runs` e zero `agent_proposals`. As flags
`feature_openclaw` e `feature_ai_swarm` continuam `false` e os seis perfis de agente carregam.

O backup `/opt/idml-platform/backups/20260826T205408Z` passou no restore isolado com 21 tabelas e
um artefato. O código anterior está em
`/opt/idml-platform/backups/source-phase6-pre-corpus-20260826T205412Z.tar.gz`; a imagem de rollback
é `idml-foundation:phase6-pre-corpus`, ID
`sha256:538fee6c33936b57db1fc926338753e0aea5f6d8a34a6a5c3b281bedf466e6df`. OpenClaw e
os serviços Mapalead permaneceram healthy.
