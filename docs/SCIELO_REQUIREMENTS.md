# Requisitos SciELO para o perfil inicial

## Decisão de perfil

Consulta realizada em 2026-08-24.

```text
SPS_PROFILE: sps-1.10
JATS_DTD: Journal Publishing 1.3
SCOPE: SciELO Brasil, artigo de periódico, publicação contínua
```

O XML aprovado disponível no corpus é `sps-1.9` sobre JATS 1.1 e será usado como referência de conteúdo e empacotamento, não como definição normativa do XML novo. O builder deverá emitir SPS 1.10/JATS 1.3 desde o início. Perfil, DTD, regras e validadores precisam ser versionados juntos.

## Fontes oficiais consultadas

- [Guia para entrega de arquivos para publicação na coleção SciELO Brasil, versão dezembro de 2024](https://www.scielo.org/documents/57/guia_entrega_pacotes.pdf)
- [SciELO Publishing Schema — mudanças da versão 1.10](https://scielo.readthedocs.io/projects/scielo-publishing-schema/pt_BR/master/whatsnew-1.10.html)
- [Atestado de capacidade técnica, outubro de 2025](https://www.scielo.org/documents/120/Atestado_de_capacidade_tecnica_pt_rywwP0B.pdf)
- [XML Package Maker — documentação oficial](https://documentacao.scielo.org/books/scielo-pc-programs/page/xml-package-maker-xpm)
- [Instalação dos programas SciELO PC](https://documentacao.scielo.org/books/scielo-pc-programs/page/como-instalar)
- [Download dos programas SciELO PC](https://documentacao.scielo.org/books/scielo-pc-programs/page/download)
- [Comunicado oficial sobre adoção exclusiva do SPS 1.10](https://groups.google.com/g/scielo-xml/c/MJHQuqRwsgs)
- [Discussão oficial sobre falsos erros dos validadores em SPS 1.10, janeiro de 2026](https://groups.google.com/g/scielo-xml/c/g4WQoK_cGss)
- [Discussão oficial sobre versão do XPM e falsos erros, março de 2026](https://groups.google.com/g/scielo-xml/c/KiC-TDlazJE)
- [Resposta oficial que trata SPS 1.10 como versão vigente, março de 2026](https://groups.google.com/g/scielo-xml/c/OOGKe2ZICL8)

## Estrutura do artigo

O modelo e o builder deverão representar, no mínimo:

- `front`: periódico, identificadores, categoria, títulos e traduções, autores, ORCID, afiliações, datas, volume/número ou publicação contínua, licença, resumos, palavras-chave, financiamento e contagens;
- `body`: seções hierárquicas, parágrafos, listas, citações, figuras, tabelas, fórmulas, notas e referências cruzadas;
- `back`: agradecimentos, contribuições, disponibilidade de dados, conflitos, notas, grupos de referências e dados bibliográficos estruturados.

Regras obrigatórias não poderão ser inferidas somente por IA. Cada campo deve registrar origem, confiança, transformação e evidência no IDML/PDF.

## Pacote de entrega

O guia determina entrega em ZIP contendo os arquivos do artigo e o relatório do XPM. O pacote aplicável ao piloto inclui:

- XML com extensão `.xml`;
- PDF final do artigo;
- imagens em TIFF, JPG ou PNG;
- `xpm.html`;
- suplementos preferencialmente em PDF, se existirem;
- vídeo em MP4, se existir;
- tabelas e fórmulas em MathML ou LaTeX, com SVG opcional quando necessário.

Nomes de arquivos, identificador do artigo, prefixos dos assets e referências `xlink:href` devem ser consistentes. O pacote não será considerado liberável apenas porque o XML é well-formed.

## Cadeia mínima de validação

1. inspeção segura do ZIP e dos assets;
2. XML well-formed com parser sem entidades externas e sem rede;
3. validação offline pela DTD JATS 1.3 allowlisted;
4. regras SPS 1.10 disponíveis no Packtools atual;
5. checagens próprias de nomes, assets, IDs, `xref`, idioma, datas e completude;
6. construção determinística do pacote;
7. XPM em worker Windows dedicado;
8. política de release que classifica achados em bloqueadores, revisão e falsos positivos conhecidos;
9. aprovação humana quando a política exigir.

## Incompatibilidade temporária dos validadores

A adoção do SPS 1.10 precedeu a atualização uniforme de Markup, Style Checker e XPM. Comunicações oficiais de 2025 e 2026 reconhecem falsos erros. Isso não autoriza ignorar mensagens genericamente.

Será mantido um registro versionado de exceções com:

- ferramenta e versão exatas;
- regra e mensagem normalizada;
- evidência oficial que justifica a exceção;
- perfil SPS afetado;
- data de revisão e responsável;
- teste que impede mascarar erros diferentes.

Qualquer erro não reconhecido permanece bloqueador ou exige revisão humana.

## Atualização normativa

SPS 1.11/JATS 1.4 ainda não integra o escopo inicial. Uma nova versão só poderá ser adotada por novo perfil, corpus de regressão, ADR e homologação. O software não deverá sobrescrever o perfil vigente de um job já iniciado.
