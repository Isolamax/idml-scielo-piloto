# Schemas de saída dos agentes — Fase 6

Versão do contrato: `agent-proposal-1.0`.

Há um schema fechado comum e uma especialização por domínio em `schemas/agents/`. Em runtime, o
backend gera o schema inline a partir do mesmo modelo Pydantic e fixa `domain` no valor da tarefa.
Propriedades adicionais são rejeitadas.

## Campos obrigatórios

| Campo | Regra |
|---|---|
| `schema_version` | valor exato `agent-proposal-1.0` |
| `domain` | um dos seis domínios configurados e igual à tarefa |
| `patch` | 1–5 operações `replace`; caminho JSON Pointer existente, escopado e sem duplicação |
| `confidence` | número entre 0 e 1 |
| `evidence` | 1–20 referências existentes no item |
| `alternatives` | 1–10 alternativas explícitas |
| `reason` | 20–2000 caracteres, sem instruções para mudar política/release |
| `needs_human` | obrigatório; deve ser verdadeiro abaixo de 0,85 |

Uma evidência contém `evidence_id`, `source_kind`, `locator` e `excerpt_sha256`. Não basta o formato
ser válido: os quatro valores são comparados com a evidência tenant-bound entregue pelo backend.

## Domínios e caminhos

| Domínio | Prefixos permitidos |
|---|---|
| `metadata` | `/front` |
| `contributors_affiliations` | `/front/contributors`, `/front/affiliations` |
| `structure` | `/body` |
| `references` | `/back/references` |
| `figures_tables` | `/body`, `/assets` |
| `math_notes` | `/body`, `/back/notes`; piloto somente |

O prefixo do domínio é uma primeira barreira. A operação também precisa estar no campo do
`ReviewItem`, atingir um caminho existente, produzir mudança real, preservar o modelo canônico e
passar pelo build e validação JATS determinísticos.

Para `RichText`, `plain.value` e `inlines` formam um único valor semântico. Se o fragmento trouxer
`atomic_rich_text`, a proposta deve conter as duas operações indicadas: uma substitui o texto
simples e a outra substitui o array completo de inlines. A concatenação de `inline.text` deve ser
exatamente igual a `plain.value`; não é permitido alterar somente um inline individual.

## Rejeição

Saídas sem evidência, com campo extra, domínio divergente, tipo incorreto, política embutida,
locator/hash divergente, versão atrasada, snapshot fora da ponta ou custo excedido não geram
proposta aplicável. O run imutável registra somente hashes, provider/modelo, versões, tokens, custo,
latência, tentativas e código normalizado; raciocínio privado e mensagem bruta de exceção não são
persistidos.
