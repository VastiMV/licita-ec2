# Torre de Controle — como funciona

A Torre é a **tela inicial** do Licita (desde 08/11/2026). Ela acompanha cada
licitação da oportunidade até o dinheiro na conta. Este documento explica a
lógica inteira: o que é cada etapa, de onde vem cada informação e em que
arquivo está cada regra.

> **Regra de ouro:** a etapa é **calculada**, nunca gravada. Ninguém escolhe
> etapa num select nem arrasta cartão. A etapa muda quando um **fato** muda
> (uma cotação salva, uma leitura da Sentinela, um empenho no Portal da
> Transparência, uma entrega lançada). Para mudar onde um cartão aparece,
> mude o fato — ou a regra em `torre.py`, com teste.

## 1. Estágios e etapas

São **4 estágios** e **13 etapas**, nesta ordem (a ordem importa: a etapa
"mais adiante" ganha).

| Estágio | Etapa (`chave`) | Quando a licitação está nela | De onde vem o fato |
|---|---|---|---|
| Preparar | Oportunidade (`oportunidade`) | salva no Licita, no prazo, sem cotação | Licita (busca) |
| Preparar | Cotação (`cotacao`) | tem cotação salva no Cotador, no prazo | Licita (Cotador) |
| Preparar | Cadastro de proposta (`cadastro_proposta`) | a proposta (os preços) foi cadastrada no Compras.gov e a sessão ainda não abriu | Sentinela |
| Disputar | Disputa (`disputa`) | sessão aberta, item em disputa (lances) | Sentinela |
| Disputar | Aguardando julgamento (`aguardando_julgamento`) | disputa encerrada, proposta ainda sem situação | Sentinela |
| Disputar | Julgado e habilitado (`julgado_habilitado`) | proposta **aceita** e depois **fornecedor habilitado**; com recurso aberto fica aqui com etiqueta | Sentinela |
| Disputar | Aguardando adjudicação (`aguardando_adjudicacao`) | habilitado, recurso encerrado, ainda não adjudicado | Sentinela |
| Disputar | Homologado (`homologado`) | proposta adjudicada **ou** resultado homologado no PNCP | Sentinela + PNCP (diário) |
| Contratar | Contrato (`contrato`) | contrato ou **ata** de registro de preços | PNCP (ata, diário) · contrato à mão |
| Contratar | Empenho / OF (`empenho`) | empenho ou ordem de fornecimento | Portal da Transparência (federal, diário) · OF e estados/prefeituras à mão |
| Receber | Entrega (`entrega`) | entrega lançada | à mão |
| Receber | Liquidado (`liquidado`) | liquidação | Portal da Transparência (federal) |
| Receber | Recebido (`recebido`) | pagamento | Portal da Transparência (federal) |

Coisas que **não** são etapa:

- **O PDF da proposta** (proposta comercial/ajustada). Ele é pedido **depois
  de ganhar**, durante o julgamento (convocação de anexo). Gerar o PDF não
  muda a etapa. Fica no menu em "Propostas (PDF)".
- **Recurso** — é etiqueta ("recurso até 10/11") no cartão em Julgado e
  habilitado.
- **Suspensa** — é etiqueta. A licitação continua onde estava.

## 2. A etapa é do item

Uma licitação tem vários itens, e a empresa disputa alguns. **Cada item da
empresa tem a sua etapa.** O cartão da licitação fica na etapa do item que
está **mais adiante**.

A função que decide a etapa de um item é `etapa_do_item` em
`backend/apps/licitacoes/torre.py`. Ela olha do fato mais adiantado para
trás e para no primeiro que encontra:

1. Item **perdido** → não conta (sai da conta do cartão):
   homologado para outro fornecedor, proposta desclassificada (situação
   1, 2 ou 9) ou fornecedor inabilitado (5).
2. Tem **pagamento** → Recebido.
3. Tem **liquidação** → Liquidado.
4. Tem **entrega** → Entrega.
5. Tem **empenho** ou **ordem de fornecimento** → Empenho / OF.
6. Tem **contrato** ou **ata** → Contrato.
7. Adjudicado (situação 6, fase `AE`) ou **vencedor no PNCP** → Homologado.
8. Fornecedor habilitado (4): com recurso aberto → Julgado e habilitado
   (com etiqueta); sem recurso → Aguardando adjudicação.
9. Proposta aceita (3) → Julgado e habilitado.
10. Fase do item em disputa (lances) → Disputa.
11. Fase depois da disputa, ou já tem classificação → Aguardando julgamento.
12. Senão → Cadastro de proposta.

Um item em **2º lugar ou pior** fica marcado como `perdendo` (em cinza no
cartão: "2 itens perdendo (podem ser chamados)"). Ele **não** é perdido: o
1º colocado pode ser desclassificado e o próximo é chamado.

Documentos financeiros e entregas **sem item** valem para a compra inteira
(um contrato que cobre todos os itens ganhos).

Se **todos** os itens da empresa se perderam, a licitação sai para
**Encerradas** (motivo "Perdida").

### Licitação sem dado do Compras.gov (só Preparar)

Antes da Sentinela ler alguma coisa, a etapa vem do que o Licita sabe:

- sem cotação → Oportunidade; com cotação → Cotação;
- **prazo vencido com cotação, no Compras.gov.br** → fica em Cadastro de
  proposta com a etiqueta **"confirmar com a Sentinela"**. Não dá para saber
  se a proposta foi cadastrada até a Sentinela ler. Só vale para o
  Compras.gov.br (a única plataforma que a Sentinela lê,
  `PLATAFORMA_COM_SENTINELA`);
- prazo vencido com cotação em **outro portal** → Descartadas, a não ser que
  tenha proposta gerada no fluxo antigo (aí fica em Cadastro de proposta com
  "confirmar participação").

## 3. Saídas do quadro: Encerradas e Descartadas

Regra da operação (07/11/2026): **cotar não é participar.**

| Vai para | Quando | Motivo exibido |
|---|---|---|
| **Encerradas** (participou) | todos os itens da empresa perdidos | Perdida |
| Encerradas | compra revogada, anulada, fracassada ou deserta (situação da compra no Compras.gov) | Revogada / Anulada / Fracassada / Deserta |
| **Descartadas** (não participou) | tirada da lista antes do prazo | Tirada da lista |
| Descartadas | prazo venceu sem cotação | Prazo venceu sem cotação |
| Descartadas | prazo venceu com cotação, fora do Compras.gov.br | Prazo venceu com cotação |
| Descartadas | apareceu nas participações do Compras.gov **sem proposta cadastrada** (caso do Pregão 55/2026, Cubatão) | Sem proposta cadastrada |

- **Uma licitação está em um lugar só:** no quadro, em Encerradas ou em
  Descartadas. `test_saidas.py` garante isso.
- A regra de saída mora em `torre.avaliar` (para o quadro) e em
  `encerradas.py` (como consulta no banco, para as listas filtrarem e
  ordenarem). As duas têm que concordar: se mudar uma, mude a outra e rode
  `test_saidas.py`.
- Nada é apagado. "Tirar da lista" é remoção lógica.

## 4. Registro de preços (ata)

Em registro de preços (ex.: 201/2026 UFVJM, 61/2026 IF Farroupilha) não há
contrato: há **ata**. O órgão empenha **quando precisa**, em partes, até a
ata vencer. Um item pode ter **vários empenhos**. O valor homologado é o
**teto**, não venda garantida. A sincronia do PNCP guarda a vigência e a
quantidade já empenhada da ata em `DocumentoFinanceiro.dados`.

## 5. Etiquetas e urgência

O cartão pode ter etiquetas, em 3 níveis: **alerta** (vermelho, ex.:
"proposta até amanhã", convocação), **aviso** (amarelo, ex.: recurso aberto,
"confirmar com a Sentinela") e **info**. A borda do cartão acende com a cor
da mais grave. **A cor nunca é a única pista:** o texto da etiqueta diz o
porquê.

Ordem dos cartões em cada estágio (`_urgencia`): alerta primeiro, depois
aviso, depois o prazo mais curto.

## 6. Os dados (models)

Todos em `backend/apps/licitacoes/models.py`. Foram **acrescentados** ao lado
do que existia (nenhuma migração apagou nada).

| Model | O que guarda | Quem preenche |
|---|---|---|
| `OportunidadeSalva` | a licitação (já existia); ganhou `numero_processo` | busca do Licita, ou a sincronia do PNCP (cria a salva de uma vitória que não estava no Licita) |
| `ParticipacaoCompra` (1 por salva) | o que o Compras.gov diz da compra: fase, situação (PD/SU/RE/AN/FR/DE), se tem proposta cadastrada, diligência/convocação em andamento, quando a sessão abre, fonte | Sentinela (ainda não existe) |
| `ItemParticipado` (N por salva) | cada item da empresa: número, descrição, quantidade, marca/modelo, classificação, situação da proposta, fase do item, valores (inicial, lance, negociado, homologado), recurso, `vencedor_e_a_empresa` | Sentinela · PNCP (vitórias) |
| `DocumentoFinanceiro` (N por salva, opcional por item) | contrato, ata, empenho, ordem de fornecimento, liquidação, pagamento: número, data, valor, fonte, dados brutos. Pode ficar **sem licitação** até alguém ligar | PNCP (ata) · Portal da Transparência · à mão |
| `Entrega` (N por salva) | data, nota fiscal, observação | à mão |

Códigos do Compras.gov (fase da compra, fase do item, situação da proposta)
estão como constantes no topo de `torre.py`. A fonte é a lista pública
`comprasnet-fase-externa/v1/enums`.

## 7. Sincronias diárias (sozinhas)

Rodam no Celery Beat, no horário de Brasília, **de segunda a sexta** (fim
de semana não tem movimentação). Agendadas por migração (`0007`, `0009` e
`0010`, que passou para dias úteis), então já nascem ligadas em qualquer servidor.

| Hora | O quê | Arquivo | Rodar à mão |
|---|---|---|---|
| 8h | **PNCP**: itens homologados para os CNPJs ativos em Cadastros › Empresas e itens de ata. Cria a salva se a vitória não estava no Licita | `sincronia_pncp.py` | `manage.py sincronizar_pncp` |
| 8h10 | **Portal da Transparência**: empenho, liquidação e pagamento (federal), ano atual e anterior. Liga à licitação pelo **número do processo** (só dígitos, também quando vem na observação) ou, sem processo, pela **UG = UASG** quando há uma única licitação ganha naquela unidade | `sincronia_transparencia.py` | `manage.py sincronizar_transparencia` |

- As duas são **idempotentes**: rodar de novo atualiza, não duplica.
- Uma ligação feita à mão nunca é desfeita pela sincronia.
- A API de Dados Abertos aceita no máximo **365 dias por consulta**; o
  cliente (`integracoes/clients/compras_gov.py`, `_paginar_por_periodo`)
  divide sozinho.
- O Portal precisa da chave `PORTAL_TRANSPARENCIA_CHAVE` no `.env` do
  servidor (passo a passo em `deploy/ec2/README.md`). Sem a chave, a
  sincronia só avisa no log e não roda.
- **Estados e prefeituras** não estão no Portal da Transparência federal:
  para eles empenho, liquidação e pagamento são lançados à mão.
- **Contratos no PNCP** ainda não são lidos: o módulo de contratos da API
  estava instável (Comunicado nº 18/26) e não havia contrato real para
  conferir o formato. Contrato é lançado à mão.

## 8. API

Todas em `/api/licitacoes/`, exigem login.

| Rota | O quê |
|---|---|
| `GET torre/` | o quadro inteiro: estágios, etapas com totais, cartões já ordenados, e quantas saíram (encerradas/descartadas) |
| `GET/POST salvas/<id>/documentos-financeiros/` | lista / lança à mão (contrato, OF, empenho de estado ou prefeitura…) |
| `GET/POST salvas/<id>/entregas/` | lista / lança entrega |
| `DELETE documentos-financeiros/<id>/`, `DELETE entregas/<id>/` | apaga — **só o que é manual**; o que veio de sincronia não se apaga |
| `GET documentos-financeiros/sem-licitacao/` | o que o Portal trouxe e não deu para ligar |
| `POST documentos-financeiros/<id>/ligar/` | liga a uma licitação (e item, opcional) |
| `GET encerradas/`, `GET descartadas/` | as listas de saída, com filtros |
| `GET ciclo/` | **legado**: o quadro antigo. Nenhuma tela usa mais; sai em `feat-remover-legado` |

O cartão (`montar_torre` → `_cartao`) já vem pronto para a tela: etapa,
rótulo, `compra` ("Pregão 112/2026", tirado do código da compra no link do
Compras.gov: UASG + modalidade + número + ano), itens com valores,
`valor_ganho`, etiquetas. Em Preparar também vem a salva inteira e o
`cotacao_id`, para abrir os modais que já existem.

## 9. As telas

Frontend em `frontend/src/app/pages/torre/`.

| Rota | Tela | Arquivo |
|---|---|---|
| `/torre` | **tela inicial**: os 4 estágios lado a lado, cartões por urgência | `torre.page.*` |
| `/torre/estagio/<estagio>` | um estágio aberto (como o artboard "v2 · Estágio Disputar aberto"): as etapas lado a lado numa linha só, sem borda em volta, e os outros estágios recolhidos em faixas encostadas no menu (os de antes) e no fim da janela (os de depois) | `estagio/` |
| `/torre/etapa/<etapa>` | a lista de uma etapa (tabela) | `etapa/` |

- **Cartão** (`torre-cartao/`): pílula com a etapa, UASG, órgão, compra e
  item ("Pregão 61/2026 · item 22"), posição e conta ("1º lugar · 20 ×
  R$ 11.999,00 = R$ 239.980,00"), trilha das próximas etapas, etiquetas.
  As frases são montadas em `torre.utils.ts` (testadas em
  `torre.utils.spec.ts`).
- **Clique no cartão** (`torre-acoes.service.ts`): em Preparar abre o modal
  da oportunidade ou o Cotador; nos outros estágios abre a compra no
  Compras.gov em outra aba.
- **Oportunidade e Cotação** no menu abrem as listas que já existiam
  (Salvas e Cotador), não uma lista nova.
- **Menu** (`layout/sidebar/`): azul escuro, Buscar em destaque, os 4
  estágios sempre abertos, e o **número de licitações em cada etapa**
  (`contagem-do-menu.service.ts` relê `GET torre/` a cada troca de tela).
- **Topo** (`layout/topo-status/`): empresa e CNPJ, **Radar** ("em breve"),
  **Sentinela** ("não instalada") e **sino**. Mostram o estado verdadeiro:
  nada de "verde, há 2 min" enquanto a Sentinela não existe.
- **Visual:** segue o protótipo "Licita v1.0"
  (https://claude.ai/artifact/ET6ZEAExDHZRCfk5rNPyac, artboards "v2"). Cores
  em `frontend/src/styles/_tokens.scss` (`--color-menu-*`, `--color-coluna*`,
  `--color-etapa-*`); letra Plus Jakarta Sans.

## 10. Testes

| O quê | Onde |
|---|---|
| Regra de cada etapa, com os casos reais (61, 56, 112, 201, 55) | `backend/apps/licitacoes/test_torre.py` |
| Uma licitação em um lugar só (quadro × Encerradas × Descartadas) | `test_saidas.py` |
| Lançamentos manuais | `test_lancamentos.py` |
| Sincronias (formato real das APIs, sem rede) | `test_sincronia_pncp.py`, `test_sincronia_transparencia.py` |
| Clients | `apps/integracoes/test_compras_gov.py`, `test_transparencia.py` |
| Telas | `*.spec.ts` ao lado de cada arquivo em `pages/torre/` e `layout/` |

Para mudar uma regra: escreva o teste com o caso real primeiro, veja falhar,
mude `torre.py` (e `encerradas.py`, se for saída), rode tudo.

## 11. O que ainda não existe

Em ordem de prioridade (combinado com a operação):

1. **Sentinela v1.0** — sem ela, tudo do estágio Disputar só anda pelo PNCP
   (depois da homologação). Plano e limites em
   [`SENTINELA.md`](SENTINELA.md).
2. **Avisos no Telegram** — convocação, diligência, pedido de desconto,
   recurso, empenho, pagamento, cobrança.
3. **Radar** — sugestões de licitação parecidas com as que a empresa ganhou.
4. **Telas de lançamento manual** — a API existe (contrato, OF, entrega,
   ligar documento "sem licitação"); falta o formulário na tela.
5. **Prazo de validade da proposta** (Lei 14.133, art. 90, §3º) e lembrete
   de cobrança por dias parados.
6. **Contratos pelo PNCP**, quando o módulo estabilizar e houver um contrato
   real para conferir.

O plano detalhado, com caixas de seleção, está em
[`Tarefas/feat-torre-de-controle.md`](Tarefas/feat-torre-de-controle.md).
