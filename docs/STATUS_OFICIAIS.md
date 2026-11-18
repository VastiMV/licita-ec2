# Status oficiais × Licita

Mapa de **todos os códigos de situação e fase** do Compras.gov.br e do PNCP,
com o que o Licita faz com cada um e o nome que aparece na tela. Serve para
**consulta** (o que significa este código?) e para **decisão** (o Licita
trata isso do jeito certo?).

Levantamento de 14/11/2026, sobre o código do commit `9add351` (Sentinela
0.2.6). Quando uma regra mudar, atualize a linha aqui no mesmo PR (regra do
`AGENTS.md`).

!!! warning "Nada aqui foi mudado no código"
    Este documento só **descreve**. Os pontos marcados com ⚠️ ou ❌ estão
    em [Decisões pendentes](#4-decisoes-pendentes), todos **a confirmar**
    pela operação.

## 1. De onde vêm os nomes oficiais

| Fonte | O que dá | Acesso |
|---|---|---|
| **Lista oficial de códigos do Compras.gov.br**: `https://cnetmobile.estaleiro.serpro.gov.br/comprasnet-fase-externa/v1/enums` e `/comprasnet-disputa/v1/enums` | Código, nome técnico e nome de tela de **cada** fase e situação (compra, item, proposta, recurso, diligência, envio ao PNCP…). Cópia de 14/11/2026 em [`referencia/`](referencia/README.md) | 🌐 aberta, sem login |
| **Manual PNCP API Consultas v1.0**, seção 5 (tabelas de domínio) | Situação da contratação, do item, do resultado, modalidade, modo de disputa, tipos de contrato | 🌐 gov.br/pncp |
| **Lei 14.133/2021** | Fases (art. 17), decisão final (art. 71), recursos (art. 165) | — |
| **Manuais do Compras.gov.br** (Pregão Eletrônico 14.133 Visão Governo e Fornecedor, Nova Sala de Disputa) | O que acontece em cada tela | 🌐 gov.br/compras |

!!! info "O PNCP não vê o meio do processo"
    No PNCP o item fica **Em Andamento** do edital até a homologação. Abertura,
    lances, julgamento, habilitação e recurso **só existem no Compras.gov.br**.
    A API de Dados Abertos (`dadosabertos.compras.gov.br`, Lei 14.133) usa os
    **mesmos códigos do PNCP**. Por isso a Sentinela é a única fonte do Licita
    para as fases 3 a 8 abaixo.

## 2. Fase por fase

Legenda da coluna Licita: ✅ trata certo · ⚠️ trata, mas diverge do oficial
· ❌ não trata. Entre aspas, o nome que aparece na tela do Licita.

| # | Fase (Lei 14.133) | Compras.gov.br | PNCP | Licita |
|---|---|---|---|---|
| 0 | Planejamento (art. 17, I) | Compra `5` Carregando da Fase Interna · `6` Aguardando publicação | nada | ✅ não vê; 5 e 6 contam como "antes da sessão" |
| 1 | Divulgação do edital (art. 17, II) | Compra `PD` Publicada/Divulgada · fase `1` Aguardando abertura · item `AS` | Contratação `1` Divulgada · item `1` Em Andamento | ✅ "Oportunidade" → "Cotação" (Preparar) |
| 2 | Cadastro de propostas (art. 17, III) | Item continua `AS`; proposta sem situação | nada muda | ✅ sem preço "Cadastro de proposta"; com preço "Aguardando sessão"; sem proposta → Descartadas "Sem proposta cadastrada"; retirada → "Proposta retirada" |
| 3 | Abertura e análise (art. 17, III) | Compra `99` Disputa agendada → `2` Em análise · item `AP` → `F` · proposta `1` desclassificada na análise | nada muda | ⚠️ `AP`/`F` viram "Aguardando sessão" com a sessão aberta · ✅ `1` → perdido "proposta desclassificada" |
| 4 | Lances (art. 17, III; art. 56; art. 60) | Compra `3` · item `AA LA LF AL FE RA AF AM DM A7 D7 DF B3 JT` · `LS` suspensa · proposta `9` | nada (lances não vão) | ✅ "Disputa" · ⚠️ `LS` sem aviso de suspensão |
| 5 | Julgamento (art. 17, IV) | Compra `4` · etapa `JP` · item `E` → `JE` · proposta `3` aceita / `2` desclassificada · desconto, anexo, diligência · cota `7`/`8` | nada muda | ✅ `E` "Aguardando julgamento" · ⚠️ `3` vira "Aceita e habilitada" antes de habilitar · ❌ diligência `C` · ❌ cota |
| 6 | Habilitação (art. 17, V) | Etapa `HF` · item `HE` · proposta `4` habilitado / `5` inabilitado · `PE PR JR` | nada muda | ✅ `4` "Habilitada (aguardando adjudicação)" · ✅ `5` perdido · ⚠️ `JE HE PE PR` sem situação → "Aguardando julgamento" |
| 7 | Recursos (art. 17, VI; art. 165) | Etapa `FR` · item `AR AC D1 D2` · decisão `P N M R` | nada muda | ✅ alertas de recurso e decisão · ⚠️ fase `AR…D2` só usada se a empresa está habilitada |
| 8 | Adjudicação (art. 71, IV) | Etapa `AH` · item `AE` · proposta `6` adjudicada | nada ainda | ⚠️ "Homologado" (decisão de 08/11/2026; o nome antecipa) |
| 9 | Homologação (art. 17, VII; art. 71, IV) | Item homologado · envio `PS → PP → SP` · erro `EP` | Item `2` Homologado · resultado `1` Informado | ✅ "Homologado" / perdido "homologado para outro fornecedor" · ❌ envio ao PNCP não lido |
| 10 | Fim sem vencedor (art. 71, II e III) | Compra `SU RE AN FR DE` · motivo da suspensão · item `2–9, 13, 14` | Contratação `2 3 4` · item `3 4 5` | ✅ `RE AN` Encerradas + sino · ⚠️ `FR DE` sem sino · ⚠️ PNCP `2 3` só etiqueta · ❌ situação do **item** |
| 11 | Contrato e execução (art. 90; Lei 4.320, art. 63) | ARP, Contratos.gov.br | Tipos de contrato `1–12` · termos `1–3` | ✅ "Contrato", "Empenho / OF", "Entrega", "Liquidado", "Recebido" |

## 3. Código por código

### 3.1 Situação da compra — `SituacaoCompraFaseExternaEnum`

Lido em `ParticipacaoCompra.situacao_compra` (`torre.py`, `sentinela/ingestao.py`).

| Código | Nome oficial | Licita | Na tela |
|---|---|---|---|
| `PD` | Publicada/Divulgada | ✅ | nada (normal) |
| `SU` | Suspensa | ✅ | etiqueta "Compra suspensa" + sino |
| `RE` | Revogada | ✅ | Encerradas "Revogada" + sino vermelho "Compra revogada" |
| `AN` | Anulada | ✅ | Encerradas "Anulada" + sino vermelho "Compra anulada" |
| `FR` | Fracassada | ⚠️ | Encerradas "Fracassada", **sem sino** ([D6](#d6)) |
| `DE` | Deserta | ⚠️ | Encerradas "Deserta", **sem sino** ([D6](#d6)) |

### 3.2 Fase da compra — `FaseCompraFaseExternaEnum`

Lido em `ParticipacaoCompra.fase_compra`.

| Código | Nome oficial | Licita | Regra |
|---|---|---|---|
| `6` | Aguardando publicação | ✅ | antes da sessão |
| `5` | Carregando compra da Fase Interna | ✅ | antes da sessão |
| `1` | Aguardando abertura da sessão pública | ✅ | antes da sessão; sem data e prazo vencido → "Sem prazo definido" |
| `99` | Disputa Agendada | ✅ | antes da sessão |
| `2` | Em análise de propostas | ✅ | depois da sessão (sem regra própria) |
| `3` | Disputa iniciada | ✅ | sem itens lidos e com proposta → "Disputa" |
| `4` | Seleção de fornecedores iniciada | ✅ | depois da sessão; a etapa vem dos itens |

### 3.3 Fase do item — `FaseItemEnum`

Lido em `ItemParticipado.fase_item`. Grupos em `torre.py`
(`FASES_ITEM_EM_DISPUTA`, `FASE_ITEM_ABERTURA_SUSPENSA`,
`FASES_ITEM_DEPOIS_DA_DISPUTA`, `FASES_ITEM_JULGAMENTO_ENCERRADO`,
`FASES_ITEM_EM_RECURSO`, `FASE_ITEM_ADJUDICADO`). Atualizado com o GEN-83
(14/11/2026).

| Código | Nome oficial | Licita | Etapa |
|---|---|---|---|
| `AS` | Aguardando abertura da sessão pública | ✅ | com preço "Aguardando sessão"; sem preço "Cadastro de proposta" |
| `AP` | Pendente da análise de propostas | ✅ | "Disputa" (antes dos lances; GEN-82) |
| `F` | Aguardando disputa | ⚠️ | "Aguardando sessão" ([D8](#d8)) |
| `AA` `LA` `LF` `AL` `FE` `RA` `AF` | Etapas aberta/fechada, encerramento, reinício | ✅ | "Disputa" |
| `AM` `DM` `A7` `D7` `DF` | Desempates (ME/EPP, 7174, disputa final art. 60) | ✅ | "Disputa" |
| `B3` `JT` | Decisão sobre cota · julgamento de técnica | ✅ | "Disputa" |
| `LS` | Abertura Suspensa | ✅ | "Aguardando sessão" (GEN-82) |
| `E` | Disputa Encerrada | ✅ | "Aguardando julgamento" |
| `JR` | Julgamento/Habilitação reabertos | ✅ | "Aguardando julgamento" |
| `JE` | Julgamento encerrado | ✅ | sem proposta aceita/habilitada/adjudicada: perdido "julgamento encerrado sem a Inside" → Encerradas, **lido a cada ronda** (GEN-78) |
| `HE` | Habilitação encerrada | ✅ | sem proposta aceita/habilitada/adjudicada: perdido "habilitação encerrada sem a Inside" → Encerradas, vigia diária (GEN-78) |
| `PE` | Aguardando encerramento | ⚠️ | "Aguardando julgamento"\* ([D4](#d4)) |
| `PR` | Aguardando reabertura | ⚠️ | "Aguardando julgamento"\* ([D4](#d4)) |
| `AR` `AC` `D1` `D2` | Recursos, contrarrazões, decisão, revisão | ✅ | "Recursos" + vermelho (item vivo, qualquer posição; GEN-83) |
| `AE` | Adjudicação encerrada (`APTO_HOMOLOGACAO`) | ✅ | "Finalizadas" (GEN-78) |

\* Só quando a proposta da empresa não tem situação. Com situação, ela manda.

### 3.4 Situação da proposta da empresa — `SituacaoPropostaItemEnum`

Lido em `ItemParticipado.situacao_proposta`.

| Código | Nome oficial | Licita | Na tela |
|---|---|---|---|
| `1` | Desclassificada na análise | ✅ | perdido "proposta desclassificada" |
| `9` | Desclassificada na sala de disputa | ✅ | perdido "proposta desclassificada" |
| `2` | Desclassificada no julgamento | ✅ | perdido "proposta desclassificada" |
| `3` | Proposta aceita | ✅ | "Propostas aceitas" (GEN-83) |
| `4` | Fornecedor habilitado | ✅ | "Habilitada (aguardando adjudicação)"; com recurso aberto, "Recursos" + vermelho |
| `5` | Fornecedor inabilitado | ✅ | perdido "fornecedor inabilitado" |
| `6` | Proposta adjudicada | ✅ | "Finalizadas", como `AE` (GEN-78) |
| `7` | Pendente aceite para assumir cota | ❌ | guarda o código, sem regra ([D7](#d7)) |
| `8` | Recusa para assumir cota | ❌ | guarda o código, não conta como perdido ([D7](#d7)) |

### 3.5 Situação do item na compra — `SituacaoItemCompraEnum`

**Não é lida.** O campo `situacao` do item chega nas capturas da Sentinela
(ver `apps/sentinela/exemplos/meus_itens_56.json`: `"situacao": "1"`), mas
`ingestao.py` só grava `fase`. ([D1](#d1))

| Código | Nome oficial | Licita |
|---|---|---|
| `1` | Ativo | — (normal) |
| `2` | Cancelado | ❌ |
| `3` / `13` | Anulado / anulado por evento | ❌ |
| `4` / `14` | Revogado / revogado por evento | ❌ |
| `5` | Suspenso | ❌ |
| `6` | Deserto | ❌ |
| `7` `8` `9` | Fracassado na análise / no julgamento / na disputa | ❌ |

### 3.6 Recurso — `SituacaoRecursalEnum`

Lido em `ItemParticipado.decisao_recurso` (vale a revisão da autoridade, se houver).

| Código | Nome oficial | Licita | Na tela |
|---|---|---|---|
| — | recurso cadastrado, sem decisão | ✅ | vermelho "recurso de {empresa} · contrarrazões até dd/mm" ou "· aguardando decisão" + sino |
| `P` | Procede | ✅ | vermelho "recurso procedente" |
| `R` | Revertida decisão não procede | ✅ | vermelho "recurso procedente" |
| `N` | Não procede | ✅ | cinza "recurso indeferido" |
| `M` | Mantida decisão não procede | ✅ | cinza "recurso indeferido" |

### 3.7 Pedidos à empresa

| Campo / enum | Código | Nome oficial | Licita | Na tela |
|---|---|---|---|---|
| Convocação de anexo (`SituacaoSolicitacaoAoParticipanteEnum`) | `S` | Solicitada | ✅ | vermelho "convocação: enviar anexo · item N" |
| | `P` | Parcialmente encerrada | ⚠️ | guarda, **não avisa** ([D5](#d5)) |
| | `E` | Encerrada | ✅ | nada |
| Negociação (`situacaoUltimaNegociacao`) | `E` | Encerrada | ✅ | nada |
| | outro | em andamento | ✅ | vermelho "pedido de desconto · item N" |
| Diligência (`SituacaoDiligenciaEnum`) | `A` | Em andamento | ✅ | vermelho "diligência · item N" (sem o campo `situacao`, também conta: lado seguro) |
| | `E` | Encerrada | ✅ | não conta |
| | `C` | Cancelada | ✅ | não conta ([D2](#d2), GEN-76) |

O código de `situacaoUltimaNegociacao` não aparece na lista oficial; o
Licita trata "tudo que não é `E`" como em andamento.

### 3.8 PNCP

| Tabela | Código | Nome oficial | Licita | Na tela |
|---|---|---|---|---|
| Situação da contratação (`conferencia_diaria.py`, 1x/dia) | `1` | Divulgada no PNCP | ✅ | nada |
| | `2` | Revogada | ⚠️ | etiqueta "Revogada (PNCP)" + sino; **fica na Torre** ([D6](#d6)) |
| | `3` | Anulada | ⚠️ | etiqueta "Anulada (PNCP)" + sino; **fica na Torre** ([D6](#d6)) |
| | `4` | Suspensa | ✅ | "Compra suspensa" + sino |
| Situação do item | `1` | Em Andamento | — | só na busca |
| | `2` | Homologado | ✅ | pelo resultado: "Homologado" ou perdido "homologado para outro fornecedor" |
| | `3` | Anulado/Revogado/Cancelado | ❌ | só na busca ([D1](#d1)) |
| | `4` | Deserto | ❌ | só na busca ([D1](#d1)) |
| | `5` | Fracassado | ❌ | só na busca ([D1](#d1)) |

### 3.9 Códigos oficiais que o Licita não lê

| Enum | Códigos | Para que serviria |
|---|---|---|
| `SituacaoEnvioResultadoEnum` | `PS PG` em processo de homologação · `PP GP` enviando ao PNCP · `SP` enviado ao PNCP · `EP ES` erro · `CG CS CE CP` cancelamento | saber **quando** o resultado chega ao PNCP |
| `EtapaSelecaoFornecedoresEnum` | `JP` julgamento · `HF` habilitação · `AH` adjudicação/homologação · `FR` recursal | etapa da compra sem depender do item |
| `CodigoRetornoSituacaoSessaoPublicaEnum` | `1` não abriu · `2` aberta · `3` suspensa · `4` encerrada | situação da sessão |
| `TipoSuspensaoCompraEnum` | `3` administrativa · `12` cautelar · `13` judicial · `14` abandono | motivo da suspensão |
| `SituacaoRemanescenteEnum` | `RE PA AH IN DE NM NF FF NA AD` | situação da empresa na convocação de remanescentes (hoje só sim/não: "convocação em andamento") |
| `SituacaoParticipanteDisputaEnum` | `G` ganhando · `E` empatado · `P` perdendo | o Licita calcula sozinho (👍 🟠 👎); não precisa |

## 4. Decisões pendentes

Ordenadas por impacto. Cada uma tem a recomendação de quem levantou, mas
**a decisão é da operação** (`AGENTS.md`, regra 1). Ao decidir, anote aqui a
data, quem decidiu e o porquê no cartão da decisão (GEN-75 a GEN-82) e aqui.

| Decisão | Situação em 18/11/2026 |
|---|---|
| D2 | decidida e feita (18/11/2026, GEN-76) |
| D1 · D5 · D7 | a confirmar (sem decisão) |
| D3 · D4 · D6 · D8 | decididas em parte pelo Carlinhos; o que falta está em cada uma |

As decisões de 14/11 descrevem como **deve ficar**. As tabelas das seções
2 e 3 continuam descrevendo como o código **está hoje**, até cada PR mudar.

### D1 — Item cancelado, deserto ou fracassado fica preso na Torre {#d1}

- **O que acontece:** a compra continua ativa, mas um item morre (cancelado,
  revogado, deserto, fracassado). O Compras.gov.br informa isso no campo
  `situacao` do item; o Licita não lê. O item fica parado em "Aguardando
  julgamento" ou na etapa em que estava.
- **Onde:** `sentinela/ingestao.py` (grava só `item.fase`), `torre.py`
  (`etapa_do_item`).
- **Opções:** (a) ler `situacao` do item e mandar para Encerradas com o
  motivo oficial; (b) ler e só mostrar etiqueta; (c) deixar como está.
- **Recomendação:** (a), com os motivos "Item cancelado", "Item deserto",
  "Item fracassado". A situação do item no PNCP (`3 4 5`) pode servir de
  segunda fonte.
- **Status:** a confirmar. Cartão: GEN-75.

### D2 — Diligência cancelada aparece como aberta {#d2}

- **O que acontece:** o código oficial é `A` em andamento, `E` encerrada,
  `C` cancelada. O Licita só descarta `E` e `F`. Uma diligência `C` gera o
  alerta vermelho "diligência".
- **Onde:** `sentinela/ingestao.py`, `_ler_diligencias`. O comentário do
  código diz que o formato ainda não tinha sido visto.
- **Opções:** (a) contar como aberta só `A`; (b) descartar também `C`.
- **Recomendação:** (a): segue a lista oficial e não depende de adivinhar
  outros valores.
- **Status:** decidido e feito (dona, 18/11/2026). Cartão: GEN-76.
    - **Decisão:** (a). Só `A` (em andamento) conta como aberta. `E` e `C`
      não contam. Porquê: segue a lista oficial e não depende de adivinhar
      outros valores.
    - **Lado seguro:** o formato real de uma diligência ainda não foi visto
      (só listas vazias). Se vier **sem** o campo `situacao`, ela conta como
      aberta, para não esconder um alerta caso o campo tenha outro nome.
    - **Código:** `sentinela/ingestao.py`, `_diligencia_aberta`.

### D3 — Nomes de etapa adiantados {#d3}

- **O que acontece:** proposta `3` (aceita) aparece como "Aceita e
  **habilitada**"; `AE` e `6` (adjudicada) aparecem como "**Homologado**".
  Pela lei, aceitar ≠ habilitar e adjudicar ≠ homologar (art. 71: a
  autoridade ainda pode devolver, revogar ou anular).
- **Onde:** `torre.py` (`ESTAGIOS`, `etapa_do_item`).
- **Contexto:** "Adjudicado → Homologado" é decisão registrada em
  [TORRE.md](TORRE.md) (pedido do Carlinhos, 08/11/2026). O ponto aqui é só
  o **nome**, não a regra.
- **Opções:** (a) manter; (b) renomear etapas ("Aceita / habilitada",
  "Adjudicado / homologado"); (c) etiqueta "adjudicado, falta homologar".
- **Recomendação:** (c): não mexe no quadro e deixa claro o que falta.
- **Status:** decidido em parte (Carlinhos, 14/11/2026). Cartão: GEN-77.
    - **Decisão:** os nomes do Licita devem **bater com os do Compras.gov.br**
      (lista oficial em [`referencia/`](referencia/README.md)). A fase `AE`
      sai de "Homologado" e vai para a nova fase **Recursos** (ver D4).
    - **A confirmar:** a fase da Torre agrupa vários status. Fica com nome
      curto e a etiqueta do item mostra o nome oficial? Para onde vai a
      proposta `6` (adjudicada)?

### D4 — Julgamento e habilitação já encerrados aparecem como "Aguardando julgamento" {#d4}

- **O que acontece:** `JE`, `HE`, `PE`, `PR` caem em "Aguardando
  julgamento" quando a proposta da empresa não tem situação (ex.: está em 4º).
  E as fases de recurso `AR AC D1 D2` só contam quando a empresa está
  habilitada.
- **Onde:** `torre.py` (`FASES_ITEM_DEPOIS_DA_DISPUTA`, `FASES_ITEM_EM_RECURSO`).
- **Opções:** (a) manter; (b) etiqueta com o nome oficial da fase ("Julgamento
  encerrado", "Aberto para recursos"…) em qualquer posição.
- **Recomendação:** (b): a etiqueta já existe como mecanismo; usa o nome
  oficial e não muda etapa.
- **Status:** decidido em parte (Carlinhos, 14/11/2026). Cartão: GEN-78.
    - **Decisão:** `JE` e `HE`: se algum item da Inside **ganhou** → nova
      fase **Propostas aceitas**; se nenhum ganhou → **Encerradas**.
      `AR`, `AC`, `D1`, `D2` e `AE` → nova fase **Recursos**, com aviso no
      **Telegram** a cada mudança de status. As fases novas estão no GEN-83.
    - **A confirmar:** o que conta como "ganhou" (proposta `3`/`4`/`6` ou 1º
      lugar de verdade); `AE` não é recurso no Compras.gov, confirmar;
      para onde vão `PE` e `PR`.

### D5 — Convocação de anexo parcialmente encerrada não avisa {#d5}

- **O que acontece:** `P` (parcialmente encerrada) é guardado, mas só `S`
  gera alerta.
- **Opções:** (a) avisar também em `P`; (b) manter.
- **Recomendação:** confirmar com a operação se `P` ainda pede algum envio
  da empresa. Sem esse caso real, manter.
- **Status:** a confirmar. Cartão: GEN-79.

### D6 — Revogada, anulada, fracassada, deserta: regras diferentes conforme a fonte {#d6}

- **O que acontece:**
    - Compras.gov.br `RE`/`AN` → Encerradas + sino.
    - Compras.gov.br `FR`/`DE` → Encerradas, **sem sino**.
    - PNCP `2`/`3` → só etiqueta vermelha; **continua na Torre**.
- **Onde:** `sentinela/ingestao.py` (`_gravar_participacao`), `torre.py`
  (`avaliar`), `conferencia_diaria.py`.
- **Opções:** (a) mesma regra para as duas fontes (Encerradas + sino);
  (b) manter o PNCP só como aviso, porque ele chega 1x por dia.
- **Recomendação:** (a) para o sino em `FR`/`DE`; para o PNCP, decidir se
  ele basta sozinho para encerrar (hoje é a única fonte das licitações fora
  do Compras.gov.br).
- **Status:** decidido em parte (Carlinhos, 14/11/2026). Cartão: GEN-80.
    - **Decisão:** a regra passa a ser **a mesma para as duas fontes**.
      Revogada/anulada **com cotação** (Licita ou Compras.gov) →
      **Encerradas, em observação**; se for **reaberta**, volta para
      **Cadastro de proposta** com a nova data. **Fracassada** com cotação →
      Encerradas **com aviso**. **Deserta** → vira o relatório de
      oportunidade (GEN-85).
    - **⚠️ Conflito a resolver:** outro pedido do mesmo dia diz que
      revogada/anulada **no PNCP** com preço vai para **Cadastro de
      proposta**, e sem preço (ou com preço em só um dos dois) vai para
      **Oportunidades**. As duas regras não cabem juntas.

### D7 — Itens de cota sem regra {#d7}

- **O que acontece:** proposta `7` (pendente aceite para assumir cota) pede
  ação da empresa e não gera alerta. `8` (recusa para assumir cota) não
  conta como perdido.
- **Opções:** (a) `7` → alerta vermelho "assumir cota · item N"; `8` →
  perdido "recusou assumir cota"; (b) manter.
- **Recomendação:** (a).
- **Status:** a confirmar. Cartão: GEN-81.

### D8 — Fases sem grupo na Torre {#d8}

- **O que acontece:** `AP` (pendente análise) e `F` (aguardando disputa)
  mostram "Aguardando sessão" com a sessão já aberta. `LS` (abertura
  suspensa) mostra "Disputa" sem aviso.
- **Opções:** (a) `AP`/`F` → "Disputa" ou etiqueta "sessão aberta";
  `LS` → etiqueta "lances suspensos"; (b) manter.
- **Recomendação:** (a), só com etiquetas.
- **Status:** decidido em parte (Carlinhos, 14/11/2026). Cartão: GEN-82.
    - **Decisão:** `AP` → **Aguardando julgamento**. `LS` → **Aguardando
      sessão**.
    - **A confirmar:** `AP` acontece **antes** dos lances, e "Aguardando
      julgamento" fica depois de "Disputa" na Torre: confirmar. `F`
      continua sem decisão.

### Oportunidade (não é defeito)

`SituacaoEnvioResultadoEnum` diz quando o resultado foi enviado ao PNCP
(`SP`) ou deu erro (`EP`). Lendo isso, o Licita saberia **no mesmo dia** que
o item foi homologado, sem esperar a sincronia diária do PNCP.

## 5. Decisões do Carlinhos (14/11/2026)

Dezesseis pedidos, cada um ligado a um cartão GEN (rótulo
`decisao-carlinhos-14-11`). O que ainda precisa de resposta está em
"A confirmar" no próprio cartão. **Nenhum foi feito no código ainda.**

| # | Decisão | Cartão |
|---|---|---|
| 1 | Disputar ganha 3 fases: **Propostas aceitas**, **Finalizadas** e **Recursos** · **feito no GEN-83** (ordem: aceitas → habilitada → recursos → finalizadas) | GEN-83 |
| 2 | `AP` (pendente da análise de propostas) → **Disputa** (revisto pela Vasti: é antes dos lances) · **feito no GEN-83** | GEN-82 ([D8](#d8)) |
| 3 | `LS` (abertura suspensa) → **Aguardando sessão** · **feito no GEN-83** | GEN-82 ([D8](#d8)) |
| 4 | `JE` (julgamento encerrado): item da Inside ganhou → **Propostas aceitas**; não ganhou → **Encerradas**, lido a cada 10 min · **feito no GEN-83** | GEN-78 ([D4](#d4)) |
| 5 | `HE` (habilitação encerrada): mesma regra do `JE` (vigia diária) · **feito no GEN-83** | GEN-78 ([D4](#d4)) |
| 6 | PNCP `2`/`3` (revogada/anulada): com preço → **Cadastro de proposta**; sem preço → **Oportunidades**, mantendo as etiquetas | GEN-80 ([D6](#d6)) |
| 7 | Card da Torre: **linha do tempo à parte** (botão ou janela) e resumo da participação: cotação, itens, preço, ganhou/perdeu e por quanto | GEN-84 |
| 8 | Revogada/anulada: **mesma regra para Compras.gov e PNCP**; com cotação → Encerradas **em observação**; reaberta → volta para Cadastro de proposta com a nova data | GEN-80 ([D6](#d6)) |
| 9 | Fracassada com cotação → Encerradas **com aviso**. Deserta → **relatório** de oportunidade (a Inside não fez proposta) | GEN-80 ([D6](#d6)) · GEN-85 |
| 10 | Compra `2` (em análise de propostas) → **Disputa** (revisto pela Vasti) · **feito no GEN-83** | GEN-86 |
| 11 | Compra `4` (seleção de fornecedores iniciada) → **Disputa** · **feito no GEN-83** | GEN-86 |
| 12 | `AR`, `AC`, `D1`, `D2` → nova fase **Recursos** (feito no GEN-83), com **Telegram** a cada mudança (GEN-88). `AE` → **Finalizadas** (revisto: adjudicação vem depois dos recursos) | GEN-78 ([D4](#d4)) · GEN-83 |
| 13 | Toda licitação de cada tela tem que aparecer na Torre (Preparar mostrava 4, Oportunidades 13) | GEN-87 |
| 14 | Suspensa ou sem prazo: sem cotação → **Oportunidades**; com cotação → **Cadastro de proposta**; avança quando recebe data; **Telegram**; vigiar a data nova mesmo quando a compra some do Compras.gov | GEN-72 |
| 15 | Os nomes no Licita têm que **bater com os do Compras.gov.br** | GEN-77 ([D3](#d3)) |
| 16 | Para teste: **todas** as notificações vão para o Telegram | GEN-88 |

### Pontos que ainda travam o código

1. **Itens 6 e 8 se contradizem** para revogada/anulada no PNCP com preço
   (Cadastro de proposta × Encerradas em observação).
2. ~~Fase "Finalizadas"~~ · ~~item 11~~ · ~~`AE` em Recursos~~ ·
   ~~o que conta como "ganhou"~~: resolvidos com a Vasti em 14/11/2026
   ("ganhou" = proposta aceita, habilitada ou adjudicada).
3. **Item 9** citou "(RE, AN, SU)". Os códigos oficiais de fracassada e
   deserta são `FR` e `DE`; foram considerados esses.

### Fato que muda o item 16

Desde 10/11/2026, **toda notificação do sino já vai para o Telegram**
(`notificacoes/servico.py`, `avisar`), para a Vasti e o Carlinhos. O que
falta é que muitas mudanças de status **não geram notificação nenhuma**. O
GEN-88 cria o tipo "Mudança de status" para cobrir isso.
