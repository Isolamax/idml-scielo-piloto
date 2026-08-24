# Política e inventário do corpus — Fase 2

## Regra de armazenamento

O corpus é restrito e não é copiado para o Git, imagem Docker, CI ou VPS. O
repositório contém somente manifestos com caminhos lógicos, tamanho, SHA-256,
tipo, finalidade e expectativas estruturais. A verificação resolve cada caminho
dentro de um root explicitamente informado, recusa symlinks/escape e lê os
arquivos apenas para tamanho e hash, sem imprimir conteúdo.

## Conjuntos

| Corpus | Papel | Fontes | Observação |
|---|---|---:|---|
| ESA e20240086 | development/gold | 11 | IDML, XML/PDF aprovados, pacote, 5 figuras, XPM e planilha |
| RBEdu 0271764 AOP | contraste | 2 | IDML + PDF |
| RBEdu 0271764 IN_AOP | contraste | 2 | IDML + PDF |
| RBEdu 0272637 AOP | contraste | 2 | IDML + PDF |
| RBEdu 0272637 IN_AOP | contraste | 2 | IDML + PDF |
| RBEdu 0272965 AOP | homologation holdout | 2 | proibido para ajuste de regras |

Os 21 arquivos foram verificados em 2026-08-24 e coincidem com os hashes dos
manifestos. O ESA registra a ficha esperada: 10 páginas, 46 Stories, 55 frames,
3 autores, 3 afiliações, 4 seções principais, 78 parágrafos, 5 figuras, 3
tabelas, 2 fórmulas inline, 15 display, 52 referências e 4 notas.

O holdout RBEdu mede generalização estrutural, mas não homologa o template ESA.
Antes do Gate G7 será necessário obter artigos ESA independentes que não tenham
orientado parser, style mapping, prompts ou limiares.

## Direitos, confidencialidade e LGPD

- finalidade: desenvolvimento e avaliação interna autorizados pelo responsável;
- redistribuição: proibida enquanto licença específica não estiver confirmada;
- classificação: `restricted`;
- dados pessoais: nomes, afiliações e contatos podem estar presentes;
- minimização: nenhum texto integral entra no repositório ou em logs;
- anonimização: fixtures automatizadas são sintéticas; manifestos preservam
  apenas nomes técnicos necessários, hashes e contagens;
- revisão de retenção: anual;
- exclusão: exige aprovação e atualização do manifesto/auditoria;
- acesso: somente pessoas e processos autorizados, sem upload para serviços de IA
  na Fase 2.

## Integridade e mudanças

Mudança de bytes cria nova versão de manifesto; um hash nunca é atualizado
silenciosamente. Cada artigo recebe `corpus_id` estável e expectativas próprias.
Um caso não pode trocar de holdout para development sem ADR e registro de
contaminação. Duplicatas físicas são identificadas por SHA-256.

## Casos-limite já documentados

- diferença entre 4 tabelas IDML e 3 tabelas editoriais no XML ESA;
- assets externos ao pacote IDML;
- fórmulas como texto, MathML, imagem ou objeto;
- objetos soltos/ancorados e frames fora do fluxo principal;
- referências/notas que não podem ser classificadas somente por estilo;
- variação AOP/IN_AOP no mesmo artigo RBEdu;
- gold legado SPS 1.9 usado como semântica, não como norma SPS 1.10.

Esses casos devem produzir evidência, `ambiguous` ou `needs_review`; não autorizam
invenção nem perda silenciosa.

