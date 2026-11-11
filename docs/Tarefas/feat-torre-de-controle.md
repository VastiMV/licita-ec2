# feat/torre-de-controle — o ciclo inteiro, da oportunidade ao dinheiro

> **Como funciona hoje:** [`docs/TORRE.md`](../TORRE.md). Este arquivo é o
> plano: o que foi feito e o que falta.

## Onde paramos (10/11/2026, noite)

**No ar** (PRs #43 a #47):
- Compra trazida pela Sentinela é **completada pelo PNCP** (órgão, itens);
  cartão em Cadastro de proposta sem cotação abre "Iniciar cotação".
- Fornecedor sem CNPJ e sem e-mail (GEN-19; pedido de voltar atrás: GEN-54).
- Cotação com título longo deixa de dar erro.
- Etapa **Aguardando sessão** (14 etapas).
- Prazo vencido com cotação e sem participação → Descartadas (Guarulhos 461).
- `AGENTS.md`/`CLAUDE.md`: regras para agentes de IA (PR #48).

**Em aberto (Jira GEN):** GEN-48 (Encerradas: menu 10 × tela 1), GEN-56
(estudar "Acompanhando"), GEN-55 (filtro UASG em Encerradas), GEN-57
(descrição da Sentinela), GEN-58 (CI de testes), GEN-54 (CNPJ obrigatório),
GEN-45 (quedas de login), GEN-46 (vigia até o contrato), GEN-47 (tirar o
Ciclo antigo). Guarulhos 387/2026 ainda sem itens (só completa quando a
Sentinela ler a participação).

**Documentation as Code:** Fase 1 (regras) feita; Fase 2 (auditoria) em
correção (GEN-59); Fases 3 a 5 (MkDocs em `insidelicitacoes.com.br/documentacao`
atrás do login, completar a documentação, validação no GitHub) a fazer.

## Onde paramos (08/11/2026, fim do dia — histórico)

**No ar** (`https://insidelicitacoes.com.br`):
- Torre de Controle com o visual do protótipo v2; Homologado em Contratar.
- Sincronias do PNCP (8h) e do Portal da Transparência (8h10), de segunda a
  sexta. Chave do Portal no `.env`; Empresa com o CNPJ certo cadastrada.
- **Sentinela beta 0.1 instalada no PC do Carlinhos** e funcionando
  (endereço **sem** `www`). Trouxe as participações reais na primeira leitura.

**Falta o Carlinhos fazer:** abrir os **"Meus itens"** de cada compra que já
passou da sessão (56, 55, 59, 61). Até lá elas ficam em Aguardando
julgamento com o aviso "abrir a compra no Compras.gov" (desde 08/11 basta abrir a compra: a lista "Todos os itens" também traz a proposta).

**08/11 (manhã):** HAR do Cubatão (55/2026): **tem proposta** no item 2
(cadeira de rodas Dellamed D600, 29 un., R$ 1.200,00, 23º lugar, fase
"Julgamento/Habilitação reabertos"). Compra favoritada; itens 2, 3 e 4
favoritados (só o 2 com preço). `isFornecedorParticipante` veio `true` —
não serve para checar proposta sem captcha. `itens/favoritos` e
`favoritas/dentre-opcoes` não pedem captcha.

**Decisões em aberto (perguntar à operação antes de fazer):**
1. **Origem no card** — etiqueta "Licita", "Compras.gov" ou "PNCP". O
   Carlinhos não sabe de onde veio cada card. (Proposto; não confirmado.)
2. **Lixeirinha** em **Cadastro de proposta e Disputar** (pedido da
   operação, 08/11). Proposto: em Disputar, a lixeira só funciona quando o
   Licita já sabe dos itens ("meus itens" lido); antes disso fica travada,
   com um botão "Conferir no Compras.gov" que abre a tela de itens para ele.
   Com proposta → **"Parar de acompanhar"** → Encerradas ("Desistiu · 23º
   lugar"), avisando que a proposta continua no Compras.gov. Sem proposta →
   Descartadas. **Falta confirmar.**
   - Junto: **a Sentinela não pode recriar o que foi descartado.** Hoje
     `ingestao._salva_da_compra` só procura entre as ativas: uma compra tirada
     da lista volta na próxima leitura de participações. Corrigir antes da
     lixeirinha.
3. **Desfavoritar no Compras.gov** pela Sentinela — seria a primeira escrita
   dela no Compras.gov: só com o clique dele, uma compra por vez. Precisa de
   um HAR (sanitized) do Carlinhos desfavoritando **uma** compra, para saber o
   endereço. Desfavoritar não retira proposta.
4. **Regra de Cadastro de proposta** — proposto: compra nas participações,
   sessão ainda não aberta e prazo não vencido → Cadastro de proposta (hoje
   cai em Oportunidade/Cotação porque "meus itens" só existe depois da
   sessão). **Falta confirmar.** Mudar `torre.avaliar` e `encerradas.py`
   juntos (`test_saidas.py`).
5. A mensagem da operação cortou em "E as oportunidades que ele…" — perguntar
   o resto.
6. Guarulhos: o card mostra **Pregão 461/2026** (prazo 09/11); a disputa de
   terça é o **387/2026**. Conferir se são duas compras diferentes.

**Próximo (combinado):** a Sentinela ler **sozinha**, a cada 3 min, a caixa
de mensagens (sem captcha) → sino → Telegram. Depois, aviso de lance abaixo
do piso (precisa de um HAR da tela real de disputa — a do 387, terça 9h).

**Antes de terça (387, Guarulhos):** cotação salva no Cotador, senão a camada
de disputa mostra "Sem cotação".

## Estágios e etapas

| Estágio | Etapa | Como o Licita sabe |
|---|---|---|
| Preparar | Oportunidade | salva no Licita (ou favorita no Compras.gov, pela Sentinela) |
| Preparar | Cotação | cotação salva no Cotador |
| Preparar | Cadastro de proposta | proposta cadastrada no Compras.gov e sessão ainda não aberta |
| Disputar | Disputa | sessão aberta, item em disputa |
| Disputar | Aguardando julgamento | item com disputa encerrada, proposta sem situação |
| Disputar | Aceita e habilitada | proposta **aceita** (3) e depois **fornecedor habilitado** (4) |
| Disputar | Habilitada (aguardando adjudicação) | habilitado, recurso encerrado, ainda não adjudicado |
| Contratar | Homologado | proposta **adjudicada** (6) e resultado publicado no **PNCP** (era Disputar; foi para Contratar em 08/11/2026, pedido do Carlinhos) |
| Contratar | Contrato | contrato ou **ata** publicada no PNCP (registro de preços = ata) |
| Contratar | Empenho / Ordem de Fornecimento | empenho no **Portal da Transparência** (federal) ou OF lançada à mão |
| Receber | Entrega | lançada à mão |
| Receber | Liquidado | liquidação no Portal da Transparência (federal) |
| Receber | Recebido | pagamento no Portal da Transparência (federal) |

Saídas do quadro:

- **Encerradas** (participou): todos os itens da empresa desclassificados ou
  inabilitados, ou homologados para outro fornecedor; compra deserta,
  fracassada, revogada ou anulada.
- **Descartadas** (não participou): as regras de hoje, mais **`sem_proposta`**
  — aparece em "Minhas participações" sem nenhum item com preço ("meus
  itens" vazio). (O Cubatão, 55/2026, citado aqui antes, tem proposta no
  item 2 — HAR de 08/11/2026.)
- **Prazo vencido com cotação e sem dado do Compras.gov** não é descartada:
  fica em Cadastro de proposta com a etiqueta "confirmar com a Sentinela",
  até a Sentinela dizer se a proposta foi cadastrada. Só vale para compras
  do Compras.gov.br (a única plataforma que a Sentinela lê); nos outros
  portais o prazo vencido com cotação continua indo para Descartadas, a não
  ser que tenha proposta gerada no fluxo antigo.
- **Suspensa** não é saída: é etiqueta no cartão. **Recurso** também é
  etiqueta (entre Aceita e habilitada e Habilitada (aguardando adjudicação)).
- Item **perdendo** (2º lugar em diante) fica em cinza até a homologação: pode
  ser chamado como remanescente.

## Registro de preços

Em compra por registro de preços (201/2026 UFVJM, 61/2026 IF Farroupilha) não
há contrato: há **ata**, e o órgão empenha **quando precisa**, em partes, até a
ata vencer. Um item pode ter **vários empenhos**; o Licita mostra o **saldo** e
avisa quando a ata está para vencer. O valor homologado é o teto, não venda
garantida.

## Modelo (novos, ao lado do que existe)

- `ParticipacaoCompra` (1:1 com `OportunidadeSalva`): o que o Compras.gov diz da
  compra — fase (`FaseCompraFaseExterna`), situação (PD/SU/RE/AN/FR/DE), se
  há proposta cadastrada, se há diligência ou convocação em andamento, quando
  foi lida e por quem (Sentinela ou manual).
- `ItemParticipado` (N por salva): número do item, descrição, quantidade,
  marca/modelo, classificação, situação da proposta (`SituacaoPropostaItemEnum`),
  fase do item (`FaseItemEnum`), valores (inicial, lance final, negociado,
  homologado), se há recurso aberto e até quando.
- `DocumentoFinanceiro` (N por salva, opcional por item): tipo (contrato, ata,
  empenho, ordem de fornecimento, liquidação, pagamento), número, data, valor,
  fonte (PNCP, Transparência, manual), dados brutos. Aceita vários do mesmo tipo.
- `Entrega` (N por salva): data, nota fiscal, observação. Manual.

## Tarefas

### Passo 0 — rede de segurança
- [x] `atualizar.sh` faz `pg_dump` antes de cada deploy e cancela se falhar
- [x] README do EC2: como voltar um deploy

### Passo 1 — etapas novas no backend
- [x] Models `ParticipacaoCompra`, `ItemParticipado`, `DocumentoFinanceiro`, `Entrega` (migração só acrescenta)
- [x] `torre.py` (ao lado do `ciclo.py`): `ESTAGIOS` e as 13 etapas (14 desde 10/11/2026, com Aguardando sessão); regra de etapa por item; cartão com a etapa de cada item
- [x] `encerradas.py`: motivos de Encerradas (perdida, fracassada, deserta, revogada, anulada) e o descarte `sem_proposta`, com a mesma regra da Torre (`test_saidas.py` garante que cada licitação está em um lugar só)
- [x] API do quadro novo (`GET /api/licitacoes/torre/`) sem quebrar `GET /api/licitacoes/ciclo/`
- [x] Lançamento manual do que nenhum sistema informa: ordem de fornecimento e entrega, e por enquanto contrato e o empenho de estados e prefeituras (`salvas/<id>/documentos-financeiros/`, `salvas/<id>/entregas/`; apaga só o que é manual). A situação do item fica para a Sentinela beta
- [x] Testes de cada regra antes do código (casos reais: 61, 56, 112, 201, 55) — `test_torre.py`

### Passo 2 — depois da homologação, sozinho
- [x] Sincronia de segunda a sexta (8h, Celery beat) do **PNCP** por CNPJ das Empresas: resultados homologados e atas. Cria a salva se ainda não existir (`sincronia_pncp.py`, `manage.py sincronizar_pncp`). Conferida contra a API real em 07/11/2026: 18 itens e as 2 compras homologadas (IBAMA 112/2026, UFVJM 201/2026)
- [ ] Contratos no PNCP: o módulo de contratos está instável (Comunicado nº 18/26) e ainda não há contrato real da empresa para conferir o formato. Até lá, lançamento manual
- [x] Sincronia de segunda a sexta (8h10) do **Portal da Transparência** (federal): empenho, liquidação, pagamento. Liga pelo número do processo (só dígitos, também quando vem na observação) e, sem processo, pela UG quando há uma licitação ganha só naquele órgão; o que não ligar fica "sem licitação" (`documentos-financeiros/sem-licitacao/` e `.../<id>/ligar/`). A sincronia do PNCP passa a guardar o `numero_processo` da compra. Conferida contra a API real em 07/11/2026 (chave aceita; nenhum empenho ainda)
- [x] Chave do Portal da Transparência na configuração do servidor (`PORTAL_TRANSPARENCIA_CHAVE` no `.env`; passo a passo no README do EC2)
- [ ] Prazo de validade da proposta (Lei 14.133, art. 90, §3º) e lembrete de cobrança por dias parados

### Passo 3 — Telegram
- [ ] Bot e configuração do chat; envio pelo Celery (o token do bot fica no `.env`, nunca no código)
- [ ] Avisos: convocação, diligência, pedido de desconto, recurso, empenho, pagamento, cobrança, prazo de desistência

### Passo 4 — Torre de Controle (frontend), ao lado da tela atual
- [x] Quadro com os 4 estágios lado a lado, etapa em cada cartão, mais urgente no topo (`/torre`)
- [x] Estágio aberto: etapas como colunas, os outros estágios em faixas nas laterais, como no protótipo v2 (`/torre/estagio/<estagio>`)
- [x] Menu novo: Buscar no topo, 13 etapas (hoje 14), Encerradas > Descartadas, Propostas (PDF), Cadastros
- [x] Identidade do protótipo "Licita v1.0": menu azul escuro com o número de cada etapa, cartão com compra, posição, conta e trilha das próximas etapas, letra Plus Jakarta Sans
- [x] No topo: empresa, Radar ("em breve"), Sentinela ("não instalada") e sino — com o estado verdadeiro até a Sentinela beta
- [x] Publicado em produção em 08/11/2026 (sábado à noite, fora de sessão)
- [x] Lista por etapa (`/torre/etapa/<etapa>`); Oportunidade e Cotação abrem as listas de hoje
- [x] Clique no cartão: Preparar abre o modal da oportunidade ou o Cotador; o resto abre a compra na plataforma

### Passo 5 — Sentinela (extensão do Chrome) — plano e limites em [`SENTINELA.md`](../SENTINELA.md)

Beta 0.1 (08/11/2026):
- [x] Extensão (`sentinela/`): copia o que a página já recebeu (participações, uma compra, meus itens, proposta do item) — nunca consulta tela com captcha
- [x] API com chave própria (`SENTINELA_CHAVE`): `captura/`, `pulso/`, `camada/<código>/`, `estado/`
- [x] Participações criam a compra que não estava no Licita; "meus itens" grava os itens da empresa com a proposta (posição, situação, lances, marca)
- [x] Pedido de desconto e convocação de anexo viram alerta no cartão; compra sem nenhum item com preço vai para Descartadas sozinha
- [x] Camada de disputa: teto, ideal, piso, custo e lucro de cada item, da cotação
- [x] Vigia: sinal de vida a cada 3 min; o botão do topo mostra o estado real (verde / âmbar / vermelho)

Beta 0.2 (08/11/2026) — lixeira e recurso. **⏸️ EM ESPERA: construído e
testado, só na branch; NÃO publicado.** A operação quer pensar mais o
sincronismo da lixeira (Licita × Compras.gov) antes do PR e do deploy. Não
instalar a extensão 0.2 antes do deploy do backend (ela chama `tarefas/` e
`ronda/`, que ainda não existem em produção).
- [x] Lixeira em todo cartão de Preparar e Disputar: pergunta com o preço lançado, Descartadas com motivo completo (quem, quando, etapa, preço), tira o favorito no Compras.gov
- [x] A Sentinela não traz de volta o descartado; convocação traz de volta em vermelho
- [x] Sessão da aba (só na memória) + consultas sozinhas, lista fechada sem captcha
- [x] Ronda a cada 10 min: proposta, fase recursal e diligências de cada item com proposta
- [x] Recurso, contrarrazões, diligência, convocação e pedido de desconto em vermelho
- [x] Itens antes da sessão (142 com preço, 387 sem) lidos quando ele abre a compra

Próximo:
- [ ] Ler sozinha a caixa de mensagens (sem captcha)
- [ ] Aviso de lance abaixo do piso na tela de disputa (precisa de um HAR/tela real de disputa — a próxima é a do Pregão 387, Guarulhos)
- [ ] Sino do Licita com as mensagens; Telegram (Passo 3)
- [ ] Captcha apareceu → avisar o Carlinhos (hoje só a sessão caída é detectada, pela renovação que falha)

### Depois
- [ ] Telas de lançamento manual (contrato, OF, entrega, ligar documento "sem licitação") — a API já existe
- [ ] Radar: sugestões parecidas com o que a empresa ganhou
- [ ] "Hoje" e "Mensagens" no menu (dependem da Sentinela)
- [ ] Remover o quadro antigo: ver `feat-remover-legado.md`, tarefa 6
- [ ] Quando houver mais de uma empresa: `sincronizar_pncp` mostrar os CNPJs consultados e avisar quando a API falhar. Hoje um 404 da API vira "0 itens" sem aviso (`_paginar` em `integracoes/clients/compras_gov.py`), e um CNPJ digitado errado em Empresas também dá 0 sem explicar — foi o que aconteceu em 08/11/2026

## Referências

- Mapa etapa → fonte, com o que já foi confirmado: `docs/TORRE.md` (seção 1) e `docs/SENTINELA.md`
- Fluxograma das fases e protótipo da Torre: artefatos "Fases do Compras.gov" e "Licita v1.0"
- Códigos do Compras.gov: `comprasnet-fase-externa/v1/enums` (público)

## Depois do deploy

Para trazer as vitórias na hora, sem esperar as 8h do dia seguinte (no EC2):

```bash
cd /opt/licita && sudo docker compose exec backend python manage.py sincronizar_pncp
```

A API de Dados Abertos aceita no máximo 365 dias por consulta; o cliente
divide o período sozinho.

## Publicado em 09/11/2026

A lixeira e o vigia de recurso (Sentinela 0.2) saíram da espera e foram
juntados com tudo o que entrou em 08–09/11 (propostas de todos, relatório,
conferência só de leitura) e com o aviso "fora dos favoritos no Compras.gov".
Extensão 0.2.1. Ainda em aberto: o relatório das descartadas ("xeretar"),
o 2º lugar com o 1º já habilitado (🟠 ou 👎), compras de "Minhas
participações" indo para Descartadas, e a contagem de Descartadas.

