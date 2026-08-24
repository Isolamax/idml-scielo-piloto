# Corpus controlado

Os binários do corpus não entram no Git. Esta árvore contém somente manifestos,
hashes, classificação de acesso e expectativas estruturais verificáveis.

Roots locais esperados:

- `esa-e20240086.json`: diretório lógico `SCIELO/EXEMPLO`;
- `rbedu-*.json`: diretório lógico `SCIELO`.

Exemplo de verificação sem copiar ou imprimir conteúdo:

```bash
python -m idml_foundation.cli corpus-verify \
  --manifest corpus/manifests/esa-e20240086.json \
  --root /caminho/privado/SCIELO/EXEMPLO
```

`RBEdu_0272965_AOP` é holdout: não deve orientar regras, prompts ou ajustes. Os
demais casos RBEdu são apenas contraste e não ampliam o primeiro template ESA.
Um conjunto de homologação ESA independente deverá ser obtido antes do Gate G7.
