# Viabilidade do XML Package Maker (XPM)

## Classificação

```text
CLASSIFICATION: GO_WITH_CONSTRAINTS
UNTouched_LINUX_HEADLESS: NO
INTEGRATION_PATH: DEDICATED_WINDOWS_WORKER
RELEASE_ROLE: REQUIRED_EXTERNAL_GATE_WHEN_APPLICABLE
```

## Função e exigência

O [guia de entrega SciELO](https://www.scielo.org/documents/57/guia_entrega_pacotes.pdf) inclui `xpm.html` no pacote. A [documentação oficial do XPM](https://documentacao.scielo.org/books/scielo-pc-programs/page/xml-package-maker-xpm) descreve a geração dos pacotes SciELO/PMC e dos relatórios de erros. O projeto deve tratá-lo como gate externo de empacotamento, não como parser do IDML nem como único validador.

## Artefato público avaliado

- Pacote: `SciELO_XPM_4.0.096-R20231215.zip`.
- SHA-256: `1b22157b9e816255db8d8910acc46a13b78c0f286cbb68155a39a95ed0f0bdec`.
- 455 entradas; aproximadamente 18,97 MB descompactados.
- Verificação prévia: nenhuma entrada absoluta, traversal, symlink ou tamanho anômalo.
- Dependências internas: `packtools==2.4.2` e `pillow==6.2.2`.
- Release notes do pacote cobrem SPS 1.9, não SPS 1.10.

O pacote público é antigo em relação ao perfil atual. Downloads futuros deverão ser allowlisted por URL, nome, hash e revisão humana. Nenhum arquivo estranho localizado em áreas não relacionadas do FTP foi baixado ou executado.

## Spike isolado

O teste usou container Python 3.8, usuário não-root, fonte read-only e execução sem rede.

- A primeira importação tentou gravar diretamente em `/xpm/xml/app.log`, contrariando execução read-only.
- Com cópia em filesystem temporário gravável, a CLI falhou por importar Tkinter incondicionalmente e não encontrar `libtk8.6.so`.
- A distribuição pressupõe ambiente gráfico/Windows, caminhos locais, Python e Java conforme a [documentação de instalação](https://documentacao.scielo.org/books/scielo-pc-programs/page/como-instalar).

Conclusão: portar ou modificar o pacote para Linux seria uma manutenção própria frágil e poderia mudar o comportamento da ferramenta oficial. Não é o caminho inicial.

## Arquitetura aprovada

1. A aplicação constrói um pacote candidato imutável.
2. Um job envia o pacote por canal autenticado a um worker Windows dedicado.
3. O worker possui versão allowlisted de XPM, Python/Java exigidos e área temporária por job.
4. O worker executa com conta sem privilégios, sem acesso ao banco da aplicação e sem compartilhar diretórios entre empresas.
5. Retorna `xpm.html`, stdout/stderr, versão, hash do executável/pacote, timestamps e status normalizado.
6. A aplicação anexa as evidências ao job, aplica a Release Policy e nunca interpreta ausência do relatório como sucesso.
7. Timeouts, indisponibilidade ou versão divergente deixam o job em `VALIDATION_UNAVAILABLE`, nunca `READY_FOR_SCIELO`.

## Falsos positivos e licenciamento

Discussões oficiais de [janeiro de 2026](https://groups.google.com/g/scielo-xml/c/g4WQoK_cGss) e [março de 2026](https://groups.google.com/g/scielo-xml/c/KiC-TDlazJE) reconhecem falsos erros enquanto ferramentas alcançam o SPS 1.10. Toda exceção será específica e auditável.

Não foi localizado, dentro do pacote avaliado, um termo claro que autorize redistribuição modificada. Portanto:

- não redistribuir nem modificar XPM no produto sem confirmação;
- instalar o artefato oficial no worker conforme orientação SciELO;
- confirmar com SciELO a automação em ambiente de serviço antes da homologação externa;
- manter XPM desacoplado para substituição por versão oficial atualizada.

Essa pendência é uma condição de homologação, não um bloqueio para iniciar a fundação técnica e o pipeline determinístico.
