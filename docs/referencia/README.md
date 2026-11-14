# Referência: listas oficiais de códigos

Cópias da lista de códigos que o próprio Compras.gov.br publica, sem login.
Guardadas para consulta e para comparar quando o Compras.gov mudar algo.
O que cada código significa para o Licita está em
[Status oficiais × Licita](../STATUS_OFICIAIS.md).

| Arquivo | Endereço de origem | Copiado em |
|---|---|---|
| [`enums-fase-externa-2026-11-14.json`](enums-fase-externa-2026-11-14.json) | `https://cnetmobile.estaleiro.serpro.gov.br/comprasnet-fase-externa/v1/enums` | 14/11/2026 |
| [`enums-disputa-2026-11-14.json`](enums-disputa-2026-11-14.json) | `https://cnetmobile.estaleiro.serpro.gov.br/comprasnet-disputa/v1/enums` | 14/11/2026 |

Cada lista tem o nome do enum (`FaseItemEnum`, `SituacaoPropostaItemEnum`…)
e, para cada código, `value` (o que vem nos dados), `enumName` (nome
técnico) e `label` (o nome que aparece na tela do Compras.gov).

**Para atualizar:** baixe de novo os dois endereços (uma chamada cada),
salve com a data no nome e compare com a cópia anterior. Código novo ou
removido → revisar [STATUS_OFICIAIS.md](../STATUS_OFICIAIS.md).
