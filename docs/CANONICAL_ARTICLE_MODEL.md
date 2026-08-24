# Raw e Canonical Article Model — versão 1.0.0

## Limites de responsabilidade

O Raw Article Model preserva fatos observados no IDML. O Canonical Article Model
representa a semântica editorial sem depender de IDML, XML, IA ou interface. A
transformação entre ambos pertence à Fase 3; esta fase define e testa os
contratos, não implementa o parser final.

```text
artefato + locator -> Evidence -> Raw Article -> Canonical Article -> futuro builder SPS
```

## Evidência e proveniência

Toda evidência identifica:

- tipo de fonte: IDML, PDF, XML aprovado, asset, humano ou sistema;
- SHA-256 do artefato;
- caminho lógico e, quando aplicável, ID XML, página, caixa e offsets;
- hash opcional do trecho e descrição curta.

Componentes referenciam `evidence_ids`. Validadores rejeitam evidência, assets,
afiliações, frames, Stories e cross-references inexistentes. Excerpts integrais
não são necessários no modelo persistido.

## Raw Article Model

O contrato representa:

- Stories e runs de texto em ordem interna;
- Spreads, páginas, TextFrames, caixas, transformações e threads;
- estilos originais e normalizados, preservando hierarquia/propriedades;
- tabelas, células, spans e referências aos runs;
- objetos ancorados/soltos, figuras, fórmulas, mídia e assets externos;
- links, notas e evidência de origem.

IDs provenientes do InDesign são preservados em `source_self_id`; IDs internos
são separados e estáveis. O validador de grafo recusa referências órfãs e IDs
duplicados.

## Canonical Article Model

O contrato separa:

- `front`: periódico, identificadores, categoria, títulos/idiomas, autores,
  grupos, ORCID, afiliações, datas, resumos, palavras-chave, licença e funding;
- `body`: seções hierárquicas e blocos de parágrafo, lista, citação, figura,
  tabela, fórmula e nota;
- `back`: agradecimentos, contribuições, disponibilidade de dados, conflitos,
  notas e referências estruturadas;
- assets e cross-references por IDs validados.

Conteúdo inline usa uma sequência ordenada e sem perda com texto, ênfase,
strong, subscrito, sobrescrito, links, xrefs, fórmula inline e named-content. A
concatenação dos nós precisa reproduzir exatamente o valor textual; divergência
é inválida.

## Ausência e ambiguidade

Campos usam estados explícitos:

- `present`: valor não vazio e evidência;
- `missing`: nenhum valor disponível;
- `ambiguous`: ao menos duas alternativas preservadas;
- `needs_review`: valor provisório não liberável sem decisão.

Transformação, confiança e alternativas são metadados, nunca licença para criar
conteúdo. Dados obrigatórios ausentes permanecem ausentes.

## IDs, versões e persistência

`stable_id(article_key, kind, source_locator)` usa UUIDv5 em namespace fixo. O
mesmo artigo/localizador produz o mesmo ID entre retries; localizadores distintos
produzem IDs distintos.

Raw e Canonical usam `schema_version=1.0.0`, JSON canônico com chaves ordenadas e
SHA-256 do conteúdo. Os JSON Schemas ficam em `schemas/`. Migrations explícitas
convertem payloads `0.1.0` e recusam versões desconhecidas.

`DomainSnapshot` persiste payload imutável por empresa, recurso, tipo, revisão,
hash, artefato fonte e snapshot pai. Unicidade impede revisão duplicada e o
backend valida tenant em recurso, artefato e linhagem.

## Compatibilidade

- mudanças aditivas compatíveis incrementam minor;
- mudança de significado/remoção incrementa major e exige migration;
- jobs persistem a versão usada e não adotam schema novo no meio da execução;
- downgrade de banco remove somente a tabela de snapshots; downgrade semântico
  de conteúdo não é implícito;
- builder XML nunca modifica o Canonical Model em memória.
