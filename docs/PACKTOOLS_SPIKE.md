# Spike Packtools — Fase 0

## Resultado

```text
CLASSIFICATION: GO_WITH_CONSTRAINTS
LINUX_EXECUTION: PROVEN
STRUCTURED_RESULTS: PROVEN
HOST_INSTALLATION: NOT_REQUIRED
```

## Método

- Execução em container efêmero `python:3.11-slim`, sem instalação global no host.
- Fonte oficial: [scieloorg/packtools](https://github.com/scieloorg/packtools).
- Tag verificada: `4.16.11`.
- Commit: `fe1ada8cd7cc638c8eab7ab1651f3b4f891d08e7`.
- O pacote importado reportou `__version__=4.16.10`, embora a tag fosse 4.16.11. O lock futuro deve registrar tag, commit e hash da imagem/artefato, não apenas `__version__`.
- A referência de uso e catálogo XML consta no [quickstart oficial](https://github.com/scieloorg/packtools/blob/master/docs/quickstart.rst).

## Provas executadas

1. Um XML aprovado do corpus, SPS 1.9/JATS 1.1, foi selecionado como referência real.
2. Uma cópia de fixture oficial foi adaptada mecanicamente para SPS 1.10/JATS 1.3 para exercitar o motor atual; ela não foi declarada XML gold válido.
3. A API legada `packtools.XMLValidator` rejeitou SPS 1.10 com mensagem de versão não suportada.
4. A API atual `packtools.sps.validation.xml_validator.get_validation_results` processou o probe com parser seguro e sem exceções.

Resultado estruturado do probe:

| Nível | Quantidade |
|---|---:|
| OK | 970 |
| Warning | 31 |
| Error | 6 |
| Critical | 12 |
| Info | 1 |
| Total | 1.020 |

O objetivo não era aprovar o probe, mas provar execução Linux e saída processável. Ambos foram comprovados.

## Decisões de integração

- usar somente a API SPS atual; proibir a API legada no perfil 1.10;
- encapsular Packtools em adapter próprio e imagem imutável;
- processar resultados por código/regra/caminho, sem depender de texto de tela;
- montar catálogo/DTD offline e desabilitar resolução externa;
- salvar versão, commit, imagem, perfil, resultado bruto e resultado normalizado em cada validação;
- manter tests de contrato contra upgrades;
- bloquear release se o validador lançar exceção, não produzir relatório completo ou usar versão não allowlisted.

## Trabalho posterior

Na Fase 1 será criada a imagem reproduzível e o lock de dependências. Na Fase 3 o corpus gold será validado de ponta a ponta, incluindo DTD e regras próprias. Essas tarefas não alteram a conclusão de viabilidade da Fase 0.
