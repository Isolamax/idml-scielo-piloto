# Análise do modelo IDML e do corpus piloto

## Corpus selecionado

Periódico/template principal: **Engenharia Sanitária e Ambiental (ESA)**.

| Artefato | Caminho | SHA-256 |
|---|---|---|
| IDML | `C:\Users\FabianoLC\Documents\SCIELO\EXEMPLO\ESA_2024086_AOP.idml` | `8ce185f5dd03f5403a36ca7b60d9d708b95e2b334e731327dd0b568b0cd44d2c` |
| XML aprovado | `C:\Users\FabianoLC\Documents\SCIELO\EXEMPLO\1809-4457-esa-30-0825\1809-4457-esa-30-e20240086.xml` | `739b4c3247a06d6d5253ad2805fb830d09692cb306cbb5c785ad99707e539de9` |
| PDF | `C:\Users\FabianoLC\Documents\SCIELO\EXEMPLO\1809-4457-esa-30-0825\1809-4457-esa-30-e20240086.pdf` | `232fb2428bbdf344af192d24865a4e39848fd4e4fae20f2325aa9ecef6ff2496` |
| Pacote aprovado | `C:\Users\FabianoLC\Documents\SCIELO\EXEMPLO\1809-4457-esa-30-0825.zip` | `e7034e8c3503f4ed8a8506105202a2f849626d981792bda4d5f05d40924e1ff8` |
| XPM | `C:\Users\FabianoLC\Documents\SCIELO\EXEMPLO\xpm.html` | `0d1b5ea75aeca68d089389e62a696cf3b99d5b55f12db7d66dc9408468542a43` |

Há cinco JPGs correspondentes às figuras `gf01` a `gf05` e uma planilha de falsos positivos. O XML gold é SPS 1.9/JATS 1.1; sua semântica é referência, mas o alvo novo é SPS 1.10/JATS 1.3.

O pacote aprovado contém XML, PDF, cinco imagens, `xpm.html` e a planilha. O relatório XPM de 2025-06-21 registrou 0 blocking errors, 0 fatal errors, 1 error e 119 warnings, evidenciando que aprovação editorial e resultado bruto da ferramenta não são equivalentes.

## Dimensão do IDML principal

- Adobe InDesign DOM 20.3.
- 371.156 bytes e 64 entradas ZIP.
- 46 Stories, 6 Spreads e 10 páginas.
- 55 TextFrames e 52.772 caracteres de conteúdo.
- 4 estruturas `Table` no IDML.
- 24 nós de shapes dentro de Stories, usados por objetos ancorados/inline.
- 7 nós gráficos nos Spreads e nenhum arquivo incorporado em `Links/`; os assets são referenciados externamente.
- todos os 55 frames possuem atributos de encadeamento, incluindo o sentinel `n`; os fluxos maiores atravessam múltiplos frames e páginas.

O XML gold correspondente possui 3 autores, 3 afiliações, 4 seções de primeiro nível, 78 parágrafos no body, 5 figuras, 3 tabelas, 2 fórmulas inline, 15 fórmulas display, 52 referências e 4 notas.

## Corpus complementar

Também foram identificados cinco IDMLs únicos da Revista Brasileira de Educação (RBEdu), todos com PDF pareado:

| Arquivo | DOM | Páginas | Stories | Frames | Caracteres | Tabelas | Gráficos |
|---|---:|---:|---:|---:|---:|---:|---:|
| `RBEdu_0271764_AOP.idml` | 20.2 | 13 | 29 | 35 | 45.955 | 3 | 6 |
| `RBEdu_0271764_IN_AOP.idml` | 20.2 | 13 | 30 | 36 | 45.441 | 3 | 7 |
| `RBEdu_0272637_AOP.idml` | 20.3 | 20 | 33 | 45 | 71.850 | 3 | 8 |
| `RBEdu_0272637_IN_AOP.idml` | 20.3 | 20 | 42 | 54 | 69.784 | 3 | 8 |
| `RBEdu_0272965_AOP.idml` | 20.3 | 19 | 29 | 41 | 63.866 | 2 | 8 |

Esses arquivos serão corpus de contraste; não ampliam o escopo do primeiro template. Eles provam que estilos e quantidade de Stories variam mesmo entre versões AOP/IN_AOP.

## Estrutura relevante do pacote

| Origem | Uso planejado |
|---|---|
| `designmap.xml` | versão DOM, `StoryList`, recursos, Spreads e referências globais |
| `Spreads/*.xml` | páginas, frames, coordenadas, transformações, objetos e vínculo `ParentStory` |
| `Stories/*.xml` | conteúdo textual, parágrafos, caracteres, tabelas, notas e objetos inline |
| `Resources/Styles.xml` | estilos de parágrafo, caractere, tabela e célula |
| `Resources/Graphic.xml` | cores, fontes e recursos gráficos |
| `XML/*.xml` | estrutura XML associada do InDesign quando presente; não é a ordem editorial garantida |
| `META-INF/metadata.xml` | metadados XMP e versão da ferramenta |

## Estratégia de reading order

A ordem lexicográfica de `Story_*.xml`, a ordem do ZIP e `StoryList` isoladamente não representam a leitura do artigo. A estratégia tecnicamente plausível aprovada para prototipação é:

1. validar o ZIP sem extrair e construir um índice de IDs;
2. ler `designmap.xml` para preservar referências do documento;
3. ordenar Spreads e páginas pela estrutura do documento;
4. associar cada `TextFrame` a `ParentStory` e calcular sua caixa geométrica após `ItemTransform`;
5. reconstruir cada cadeia por `PreviousTextFrame`/`NextTextFrame`, detectando ciclos, gaps e frames órfãos;
6. identificar colunas por agrupamento geométrico e ordenar blocos de cima para baixo dentro da coluna, respeitando troca de página;
7. manter a sequência interna dos elementos em cada Story;
8. inserir objetos ancorados na posição do Story; para objetos soltos, usar âncora/caption, proximidade e referência textual como evidências;
9. classificar semântica inicialmente pelos estilos do template ESA;
10. comparar texto, hierarquia e contagens com PDF/XML gold; divergências geram `ReviewItem`, não reordenação silenciosa por IA.

Precedência inicial de evidências:

```text
thread explícito > âncora inline > estrutura da Story > página/coluna/geometria > estilo > heurística textual
```

Um caso em que evidências de alta prioridade conflitam deve ir para revisão humana.

## Mapeamento preliminar de estilos ESA

Os estilos observados fornecem sinais fortes:

- `01.0.titulo` e `01.1.titulo ingles`: títulos;
- `02.0.autor`: autores;
- `03.0` a `03.5`: resumo/abstract, palavras-chave, titulação e endereço;
- `04.0.sub1` e `04.1.sub2`: níveis de seção;
- `05.0.texto txt` e `05.texto primeira linha`: corpo;
- `06.0.referencias_título` e `06.1.referencias`: referências;
- `07.0` a `07.2`: títulos e conteúdo de tabelas/figuras;
- caracteres `italico`, `sobrescrito`, `subscrito` e `symbol`: marcação inline.

Nomes de estilo devem ser normalizados em Unicode sem apagar o valor original. O mapeamento será por template/periódico e versionado; não será uma tabela global hardcoded.

## PDF e fidelidade visual

As 10 páginas foram renderizadas e inspecionadas. O documento possui layout científico em duas colunas, front multilíngue, metadados laterais/rodapé, cinco figuras, três tabelas, equações, seções e referências nas páginas finais. Isso confirma a necessidade de geometria, threads e objetos ancorados.

A fidelidade será medida por:

- cobertura e ordem de texto;
- títulos/seções e níveis;
- autores/afiliações;
- figuras, tabelas e equações;
- `xref`/IDs e referências;
- diferenças permitidas de espaços, hifenização de fim de linha e Unicode.

## Avaliação do conversor legado encontrado

Foi localizado um protótipo em `C:\Users\FabianoLC\Downloads\Nova pasta\idml_converter_web`. Ele é evidência útil de tentativas anteriores, mas não será base de produção sem reengenharia porque:

- extrai ZIP com `extractall` sem a validação de traversal exigida;
- ordena Stories por nome em caminhos importantes;
- não reconstrói reading order por frames/geometria;
- contém metadados e perfil JATS hardcoded;
- mistura parser, IA e builder sem modelo canônico/proveniência suficiente;
- possui modelos de usuário simples, sem isolamento multiempresa e RBAC requerido.

O novo projeto pode reaproveitar apenas conhecimento de domínio validado pelo corpus; código deverá passar por revisão específica antes de qualquer portabilidade.

## Riscos residuais

- tabelas: há 4 estruturas no IDML e 3 no XML gold; a diferença deve ser explicada no spike do parser;
- assets externos podem não acompanhar o IDML;
- fórmulas podem aparecer como texto, MathML, imagem ou objeto externo;
- referências e notas não são confiavelmente identificadas apenas pelo estilo;
- conteúdo fora de frames principais pode ser cabeçalho, rodapé, comentário editorial ou dado científico.

Esses riscos são tratáveis no corpus e não bloqueiam o Gate G0.
