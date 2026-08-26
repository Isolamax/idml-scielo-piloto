# Métricas e critérios da Fase 2

## Normalização textual permitida

Text Fidelity aplica Unicode NFC, colapsa whitespace e remove apenas hifenização
de fim de linha seguida por continuação de palavra. Caixa, pontuação, dígitos e
conteúdo não são descartados. A similaridade determinística é calculada sobre a
sequência normalizada; o relatório deve manter contagens/diffs explicáveis.

## Métricas

- Text Fidelity: similaridade do texto esperado e produzido;
- Metadata Accuracy: campos obrigatórios corretos / esperados;
- Author e Affiliation Accuracy: entidades e vínculos exatos;
- Reference Accuracy: referências estruturadas correspondentes;
- Figure e Table Accuracy: objetos, captions, labels e assets correspondentes;
- CrossRef Accuracy: `xref` com tipo e alvo corretos; ocorrências repetidas são comparadas como
  multiconjunto por alvo, sem confundir realocação estrutural de tabelas com erro de vínculo;
- precisão/recall/F1: usados quando há conjuntos previstos versus observados;
- STP: artigos liberáveis sem revisão / artigos processados;
- Human Review Rate: artigos com pendência / artigos processados.

STP e tempo/custo serão medidos apenas quando existir pipeline. Não são simulados
na Fase 2.

## Limiar inicial do piloto

| Métrica | Target | Hard floor |
|---|---:|---:|
| Text Fidelity | 99,5% | 98,0% |
| Metadata Accuracy | 98,0% | revisão abaixo do target |
| Author Accuracy | 100% | revisão abaixo do target |
| Affiliation Accuracy | 100% | revisão abaixo do target |
| Reference Accuracy | 98,0% | revisão abaixo do target |
| Figure Accuracy | 100% | revisão abaixo do target |
| Table Accuracy | 100% | revisão abaixo do target |
| CrossRef Accuracy | 100% | revisão abaixo do target |

Esses valores congelam o baseline antes do parser. Alteração exige evidência do
corpus e revisão registrada, nunca ajuste para esconder regressão.

## Decisão

- `FAILED`: erro bloqueador, estrutura não representável ou Text Fidelity abaixo
  de 98%;
- `NEEDS_REVIEW`: ambiguidade, dado editorial pendente ou métrica abaixo do
  target sem atingir hard failure;
- `PASS`: todos os targets alcançados e nenhum bloqueador/ambiguidade.

Validade DTD/SPS, Packtools e XPM serão gates adicionais nas Fases 3 e 4. Um
`PASS` destas métricas isoladas nunca significa `READY_FOR_SCIELO`.
