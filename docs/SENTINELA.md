# Sentinela — plano da v1.0 (ainda não construída)

A Sentinela é uma **extensão do Chrome** no computador do Carlinhos. Ela é a
ponte entre o Compras.gov.br (a sessão **dele**, já logada) e o Licita. Sem
ela, o estágio Disputar da Torre só anda quando o resultado sai no PNCP.

Este documento junta o que foi pesquisado e decidido (07–08/11/2026) para
quem for construir.

## Por que extensão (e não outra coisa)

| Caminho | Por que não |
|---|---|
| Integra Compras (Serpro) | é a via oficial, mas cobra por requisição. Fora do orçamento de uma empresa de uma pessoa só que ainda não recebeu |
| Robô em servidor com a senha gov.br | guardar a senha gov.br de alguém é risco alto; **decidido: não** |
| Programa (.exe) no PC | mais difícil de instalar e atualizar que uma extensão |
| 30 abas abertas, uma por pregão | inviável para o Carlinhos |

A extensão usa a sessão que o próprio Carlinhos abriu, no navegador dele,
lendo as mesmas telas que ele leria.

## Limites que não se negociam

1. **Nunca resolver, burlar ou enganar captcha (hCaptcha).** Se aparecer um
   desafio, a Sentinela **para e avisa o Carlinhos** ("verificação pedida").
   Ele resolve com a mão dele.
2. **Nunca guardar senha** gov.br nem do Compras.gov. A sessão é a do
   navegador.
3. **Nunca marcar mensagem como lida** sem o Carlinhos abrir (abrir uma
   mensagem pela API marca como lida — só ler a **lista** não marca).
4. **Ritmo humano:** poucas leituras, em horário comercial. Nada de rajada.
5. **Só leitura** na v1.0. Ações que escrevem no Compras.gov (tirar dos
   favoritos, enviar anexo, dar lance) ficam para depois, e cada uma pede
   confirmação do Carlinhos.

## O que ela lê (v1.0)

Achados dos HARs gravados em 07/11/2026 na sessão do Carlinhos:

| O quê | Onde | Captcha? | Frequência |
|---|---|---|---|
| **Caixa de mensagens do fornecedor** — todas as licitações juntas: convocação (830), pregoeiro (840), recurso (850), impugnação (810) | `comprasnet-mensagem/v1/mensagens` | **não** | a cada ~3 min, 8h–18h |
| Contador de não lidas (leve) | `comprasnet-mensagem/v1/mensagens/quantidade-nao-lidas` | não | junto |
| Participações (fase da compra, prazo das propostas, proposta cadastrada) | `compras/participacoes` | não | 8h, 14h, 18h |
| Itens e propostas de cada participação (situação, classificação, fase do item) | `participacoes/{CNPJ}/itens/{n}/propostas` | não | 8h, 14h, 18h |
| Chat de cada pregão | — | **sim, a cada consulta** | **não usar** |

- A sessão se renova sozinha (`retoken`) quando há uso. Se cair, a
  Sentinela avisa "sessão caiu, entre de novo".
- A **convocação real** do item 22, Pregão 61/2026 (UASG 158127), veio pela
  caixa de mensagens — é o caso de teste.

## O que ela entrega ao Licita

A Sentinela manda o que leu para a API do Licita (rota a criar, autenticada
com um token **da Sentinela**, nunca a senha de ninguém). O backend grava em
`ParticipacaoCompra` e `ItemParticipado` (models já existem — ver
[`TORRE.md`](TORRE.md), seção 6) com `fonte="sentinela"`, e a Torre recalcula
as etapas sozinha.

Regras de aviso (combinadas com o Carlinhos):

- **Só alertar sobre itens em que a empresa tem proposta.** (O "item 21" do
  Pregão 61 era ruído: não era da empresa.)
- **Pedido de desconto** do pregoeiro é alerta urgente.
- Convocação, diligência e recurso aparecem no sino do Licita e no Telegram.

## O vigia (o estado no topo do Licita)

O botão "Sentinela" no topo (`layout/topo-status/`) hoje mostra "não
instalada". Com a extensão funcionando:

| Cor | Quando |
|---|---|
| Verde | leu há pouco ("há 2 min") |
| Amarelo | a sessão caiu / verificação (captcha) pedida — precisa do Carlinhos |
| Vermelho | parada (sem leitura há mais de X minutos em horário comercial) |

## Tarefas

Estão em [`Tarefas/feat-torre-de-controle.md`](Tarefas/feat-torre-de-controle.md),
"Passo 5".
