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

São **4 estágios** e **14 etapas**, nesta ordem (a ordem importa: a etapa
"mais adiante" ganha).

| Estágio | Etapa (`chave`) | Quando a licitação está nela | De onde vem o fato |
|---|---|---|---|
| Preparar | Oportunidade (`oportunidade`) | salva no Licita, no prazo, sem cotação | Licita (busca) |
| Preparar | Cotação (`cotacao`) | tem cotação salva no Cotador, no prazo | Licita (Cotador) |
| Preparar | Cadastro de proposta (`cadastro_proposta`) | aceita/cadastrada no Compras.gov, **ainda sem preço lançado** no item | Sentinela |
| Disputar | Aguardando sessão (`aguardando_sessao`) | **preço lançado** no Compras.gov e a sessão ainda não abriu (10/11/2026). Etiqueta com a data da sessão; sem cotação no Licita, avança assim mesmo com o aviso "sem cotação no Licita" | Sentinela |
| Disputar | Disputa (`disputa`) | sessão aberta, item em disputa (lances) | Sentinela |
| Disputar | Aguardando julgamento (`aguardando_julgamento`) | disputa encerrada, proposta ainda sem situação | Sentinela |
| Disputar | Aceita e habilitada (`julgado_habilitado`) | proposta **aceita** e depois **fornecedor habilitado**; com recurso aberto fica aqui com etiqueta | Sentinela |
| Disputar | Habilitada (aguardando adjudicação) (`aguardando_adjudicacao`) | habilitado, recurso encerrado, ainda não adjudicado | Sentinela |
| Contratar | Homologado (`homologado`) | proposta adjudicada **ou** resultado homologado no PNCP. Abre o estágio Contratar: ganhou, agora é esperar contrato ou empenho (pedido do Carlinhos, 08/11/2026) | Sentinela + PNCP (dias úteis) |
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
   1, 2 ou 9), fornecedor inabilitado (5) ou **1º já habilitado** (outra
   empresa à frente já foi aceita/habilitada; 09/11/2026). Exceção:
   convocação, pedido de desconto ou recurso em aberto traz o item de volta.
2. Tem **pagamento** → Recebido.
3. Tem **liquidação** → Liquidado.
4. Tem **entrega** → Entrega.
5. Tem **empenho** ou **ordem de fornecimento** → Empenho / OF.
6. Tem **contrato** ou **ata** → Contrato.
7. Adjudicado (situação 6, fase `AE`) ou **vencedor no PNCP** → Homologado.
8. Fornecedor habilitado (4): com recurso aberto → Aceita e habilitada
   (com etiqueta); sem recurso → Habilitada (aguardando adjudicação).
9. Proposta aceita (3) → Aceita e habilitada.
10. Fase do item em disputa (lances) → Disputa.
11. Fase depois da disputa, ou já tem classificação → Aguardando julgamento.
12. Preço lançado (`valor_proposta_inicial`) → Aguardando sessão.
13. Senão → Cadastro de proposta.

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
- **prazo vencido com cotação, no Compras.gov.br, sem nenhuma participação
  lida pela Sentinela** → Descartadas ("Prazo venceu com cotação") já no dia
  seguinte ao prazo (decisão de 10/11/2026, Guarulhos 461/2026). Antes ficava
  em Cadastro de proposta "confirmar com a Sentinela" e, sem proposta, a
  confirmação nunca chegava. Descartadas é calculado: se a Sentinela achar a
  participação depois, a compra volta sozinha;
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
| Descartadas | prazo venceu com cotação, fora do Compras.gov.br — ou no Compras.gov.br **sem nenhuma participação** lida pela Sentinela (desde 10/11/2026) | Prazo venceu com cotação |
| Descartadas | apareceu nas participações do Compras.gov **sem proposta cadastrada** (a lista "meus itens" vem vazia) | Sem proposta cadastrada |

- **Uma licitação está em um lugar só:** no quadro, em Encerradas ou em
  Descartadas. `test_saidas.py` garante isso.
- A regra de saída mora **num lugar só**: `torre.avaliar` (desde
  09/11/2026). As listas de Encerradas e Descartadas e os números do menu
  saem dela (`encerradas.classificar`). Ao mudar, rode `test_saidas.py`.
- Nada é apagado. "Tirar da lista" é remoção lógica.

## 4. Registro de preços (ata)

Em registro de preços (ex.: 201/2026 UFVJM, 61/2026 IF Farroupilha) não há
contrato: há **ata**. O órgão empenha **quando precisa**, em partes, até a
ata vencer. Um item pode ter **vários empenhos**. O valor homologado é o
**teto**, não venda garantida. A sincronia do PNCP guarda a vigência e a
quantidade já empenhada da ata em `DocumentoFinanceiro.dados`.

## 5. Etiquetas e urgência

O cartão pode ter etiquetas, em 3 níveis: **alerta** (vermelho, ex.:
"proposta até amanhã", convocação), **aviso** (amarelo, ex.: "fora dos favoritos no
Compras.gov", "sem cotação no Licita") e **info** (ex.: "sessão 13/11 09:00"). A borda do cartão acende com a cor
da mais grave. **A cor nunca é a única pista:** o texto da etiqueta diz o
porquê.

Ordem dos cartões em cada estágio (`_urgencia`): alerta primeiro, depois
aviso, depois o prazo mais curto.

## 5b. Lixeira e recurso (08/11/2026)

**Lixeira** (`apps/licitacoes/lixeira.py`, `POST salvas/<id>/descartar/`):

- Em **todo cartão de Preparar e de Disputar**. Para o Carlinhos é uma coisa
  só: um clique, uma pergunta, e vai para **Descartadas**.
- A pergunta mostra o **preço lançado** quando a Sentinela já leu os itens
  ("Você tem preço cadastrado no item 2 (Dellamed D600, R$ 1.200,00, 23º
  lugar). Deseja prosseguir?"), ou avisa que ainda não conferiu. Nunca bloqueia.
- O motivo grava **quem, quando, em que etapa e com que preço** ("Descartada
  manualmente por Carlinhos em 09/11/2026, na etapa Aguardando julgamento.
  Tinha preço no item 2 (…)") — Descartadas e "Ver processo" mostram esse
  texto. Motivo `descartada_manual`, que vale sobre as outras regras.
- **Descartadas passa a aceitar quem participou** quando é ele que descarta
  (decisão de 08/11). As saídas automáticas continuam em Encerradas.
- No Compras.gov, a Sentinela **tira o favorito** (tarefa
  `sentinela.Tarefa`). Com preço lançado a compra continua em "Minhas
  participações" — lá fica "poluído", o Licita fica limpo.
- **A Sentinela nunca traz de volta** o que foi descartado: atualiza os fatos
  em silêncio. **Exceto convocação** (anexo pedido ou chamada de
  remanescente): a licitação volta para a Torre, em vermelho, com o evento
  "Voltou para a Torre sozinha: …".

**Vermelho = pede resposta da empresa:** convocação (anexo, remanescente),
pedido de desconto, **recurso**, diligência.

**Recurso** (`fase-recursal-fornecedor/<sessão>`, lido pela ronda da
Sentinela, sem captcha). Caso real: Pregão 56/2026, item 22 — a Brava Sul
recorreu em 05/10, o prazo de contrarrazões venceu em 09/10 sem resposta, o
recurso foi indeferido em 13/10 e mantido em 26/10. O cartão mostra:

| Situação | Etiqueta |
|---|---|
| recurso cadastrado, prazo de contrarrazões aberto | 🔴 "recurso de Brava Sul · item 22 · contrarrazões até 09/10 23:59" |
| prazo passou, sem decisão | 🔴 "recurso de … · item 22 · aguardando decisão" |
| procedente / revertido (P, R) | 🔴 "recurso procedente · item 22" |
| indeferido / mantido (N, M) | "recurso indeferido · item 22" (informação) |

## 6. Os dados (models)

Todos em `backend/apps/licitacoes/models.py`. Foram **acrescentados** ao lado
do que existia (nenhuma migração apagou nada).

| Model | O que guarda | Quem preenche |
|---|---|---|
| `OportunidadeSalva` | a licitação (já existia); ganhou `numero_processo` | busca do Licita, ou a sincronia do PNCP (cria a salva de uma vitória que não estava no Licita) |
| `ParticipacaoCompra` (1 por salva) | o que o Compras.gov diz da compra: fase, situação (PD/SU/RE/AN/FR/DE), se tem proposta cadastrada, diligência/convocação em andamento, quando a sessão abre, fonte | Sentinela |
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
| `GET/POST salvas/<id>/descartar/` | a lixeira: a pergunta (preço lançado) / descartar |
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
  **Sentinela** (verde lendo, âmbar precisa de você, vermelho parada) e
  **sino**. Mostram o estado verdadeiro.
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
mude `torre.py` (a saída também mora lá), rode tudo.

## 11. O que ainda não existe

Em ordem de prioridade (combinado com a operação):

A Sentinela (0.2.4) e os avisos no Telegram **já existem** (ver
[`SENTINELA.md`](SENTINELA.md)). Falta:

1. **Fim da vigia por contrato publicado no PNCP** (hoje: ata ou 180 dias).
2. **Telegram para empenho, pagamento e cobrança** (hoje: os avisos do sino).
3. **Radar** — sugestões de licitação parecidas com as que a empresa ganhou.
4. **Telas de lançamento manual** — a API existe (contrato, OF, entrega,
   ligar documento "sem licitação"); falta o formulário na tela.
5. **Prazo de validade da proposta** (Lei 14.133, art. 90, §3º) e lembrete
   de cobrança por dias parados.
6. **Contratos pelo PNCP**, quando o módulo estabilizar e houver um contrato
   real para conferir.

O plano detalhado, com caixas de seleção, está em
[`Tarefas/feat-torre-de-controle.md`](Tarefas/feat-torre-de-controle.md).

## Regras de 09/11/2026 (vigia, datas, acompanhadas e o sino)

A regra de "onde está cada licitação" mora **num lugar só**: `torre.avaliar`.
As listas de Encerradas e Descartadas e os números do menu saem dela
(`encerradas.classificar`) — antes havia uma cópia da regra em forma de
consulta, e o menu dizia 3 descartadas enquanto a lista mostrava 4.

| Caso | Onde fica | Aviso |
|---|---|---|
| Compra **suspensa** (Compras.gov `SU` ou PNCP) | Preparar (Oportunidade/Cotação) | "Compra suspensa" |
| Disputa agendada **sem data**, prazo vencido | Preparar | "Sem prazo definido" |
| Em "Minhas participações", prazo vencido, **sem cotação** | Encerradas · "Acompanhando o resultado" (relatório para "xeretar") | — |
| Item com o **1º já habilitado** (outra empresa) | item perdido; todos assim → Encerradas | 👎 "1º já habilitado" |
| Item perdido com **convocação**, pedido de desconto ou **recurso** pendente/procedente | volta para a Torre, de onde estiver | vermelho |

- **Sinais:** 👍 1º de verdade · 🟠 **só o próximo de verdade** (na frente dele
  sobrou só quem está sendo analisado; quem caiu não conta) · 👎 o resto.
- **Datas:** a Sentinela (compras favoritadas) e o PNCP (todas as de Preparar,
  1x por dia, servidor) atualizam o prazo; a mudança vira linha no histórico
  ("Data alterada pelo órgão: 10/11 → 17/11") e aviso no sino.
- **Vigia de quem perdeu:** todo item em que ele deu preço segue vigiado 1x por
  dia (proposta dele e recurso), esteja onde estiver, até a ata aparecer
  assinada com outra empresa (Dados Abertos, por UASG) ou 180 dias depois da
  homologação. Contrato sem ata não aparece nessa fonte: vale o limite.
- **Acompanhadas:** os itens vêm do PNCP (`ItemAcompanhado`); as propostas, da
  Sentinela, 1x por dia. Se aparecer proposta da Inside, o item vira dela e a
  licitação volta para a Torre (rede de segurança).
- **O sino** (`apps/notificacoes`): convocação, pedido de desconto, recurso,
  data alterada, compra suspensa/revogada, fora dos favoritos, resultado de
  item perdido/acompanhado e relatório completo. Uma notificação por fato
  (`chave`); cada pessoa marca as suas como lidas.
- **Conferência diária** (Celery Beat, seg–sex 7h45): `conferencia_diaria.py`.

## Regras e relatórios de 10/11/2026

- **Cotou e não participou:** prazo vencido, com cotação, compra do
  Compras.gov **fora dos favoritos** (a Sentinela conferiu) → Descartadas
  ("Prazo venceu com cotação"), sem ficar em "confirmar com a Sentinela" para
  sempre (Geriatria 34/2026). Desde a Guarulhos 461 (mesmo dia), nos
  favoritos também: sem participação lida, vai para Descartadas.
- **Relatórios › Mês a mês** (`relatorio_mensal.py`): participou (mês do
  prazo), ganhou/perdeu (mês do resultado), faturamento, lucro (só com
  cotação: preço − custo da cotação). "Perdeu por pouco" = até 5%.
- **Mercado de cada item** (`mercado.py`): descrição do edital → PDM → item
  exato do catálogo (CATMAT, semelhança ≥ 0,98) → Pesquisa de Preços, 24
  meses. Média sem valores absurdos; marcas que mais venceram; quanto ele
  ofereceu. Renovado 1x por semana na conferência diária.
- **Caixa de mensagens e Telegram:** cada mensagem nova do Compras.gov e cada
  aviso do sino vão ao Telegram dos chats em `TELEGRAM_CHAT_IDS`.

