# feat/torre-de-controle — o ciclo inteiro, da oportunidade ao dinheiro

Decisões (07/11/2026, com a operação):

- **Torre de Controle** substitui o nome "Ciclo de Licitação". O quadro tem
  **4 estágios** lado a lado, cada um com as suas **etapas**; o menu mostra
  as 13 etapas, cada uma abre a lista daquela etapa.
- **A etapa continua calculada, nunca gravada** (mesma regra de `ciclo.py`).
  O que muda são as entradas: além de cotação e proposta, passam a contar a
  **participação no Compras.gov** (por item), o **PNCP** e o **Portal da
  Transparência**.
- **A etapa é do item.** O cartão da licitação fica na etapa do item da
  empresa que está mais adiante, e mostra a etapa de cada item.
- **O PDF da proposta deixa de ser etapa.** É a **proposta ajustada**, pedida
  depois de ganhar (convocação de anexo): uma ação dentro de Julgamento.
- **Construir ao lado.** A tela atual continua funcionando até a Torre ser
  aprovada. Migrações só **acrescentam**; nada é apagado nesta feat.
- **Deploy direto em produção**, em passos pequenos, nunca em dia ou hora de
  sessão. O `atualizar.sh` faz backup do banco antes de cada deploy.

## Estágios e etapas

| Estágio | Etapa | Como o Licita sabe |
|---|---|---|
| Preparar | Oportunidade | salva no Licita (ou favorita no Compras.gov, pela Sentinela) |
| Preparar | Cotação | cotação salva no Cotador |
| Preparar | Cadastro de proposta | proposta cadastrada no Compras.gov e sessão ainda não aberta |
| Disputar | Disputa | sessão aberta, item em disputa |
| Disputar | Aguardando julgamento | item com disputa encerrada, proposta sem situação |
| Disputar | Julgado e habilitado | proposta **aceita** (3) e depois **fornecedor habilitado** (4) |
| Disputar | Aguardando adjudicação | habilitado, recurso encerrado, ainda não adjudicado |
| Disputar | Homologado | proposta **adjudicada** (6) e resultado publicado no **PNCP** |
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
  — aparece em "Minhas participações" sem proposta cadastrada (caso do
  Pregão 55/2026, Cubatão).
- **Prazo vencido com cotação e sem dado do Compras.gov** não é descartada:
  fica em Cadastro de proposta com a etiqueta "confirmar com a Sentinela",
  até a Sentinela dizer se a proposta foi cadastrada. Só vale para compras
  do Compras.gov.br (a única plataforma que a Sentinela lê); nos outros
  portais o prazo vencido com cotação continua indo para Descartadas, a não
  ser que tenha proposta gerada no fluxo antigo.
- **Suspensa** não é saída: é etiqueta no cartão. **Recurso** também é
  etiqueta (entre Julgado e habilitado e Aguardando adjudicação).
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
- [x] `torre.py` (ao lado do `ciclo.py`): `ESTAGIOS` e as 13 etapas; regra de etapa por item; cartão com a etapa de cada item
- [x] `encerradas.py`: motivos de Encerradas (perdida, fracassada, deserta, revogada, anulada) e o descarte `sem_proposta`, com a mesma regra da Torre (`test_saidas.py` garante que cada licitação está em um lugar só)
- [x] API do quadro novo (`GET /api/licitacoes/torre/`) sem quebrar `GET /api/licitacoes/ciclo/`
- [x] Lançamento manual do que nenhum sistema informa: ordem de fornecimento e entrega, e por enquanto contrato e o empenho de estados e prefeituras (`salvas/<id>/documentos-financeiros/`, `salvas/<id>/entregas/`; apaga só o que é manual). A situação do item fica para a Sentinela beta
- [x] Testes de cada regra antes do código (casos reais: 61, 56, 112, 201, 55) — `test_torre.py`

### Passo 2 — depois da homologação, sozinho
- [x] Sincronia diária (8h, Celery beat) do **PNCP** por CNPJ das Empresas: resultados homologados e atas. Cria a salva se ainda não existir (`sincronia_pncp.py`, `manage.py sincronizar_pncp`). Conferida contra a API real em 07/11/2026: 18 itens e as 2 compras homologadas (IBAMA 112/2026, UFVJM 201/2026)
- [ ] Contratos no PNCP: o módulo de contratos está instável (Comunicado nº 18/26) e ainda não há contrato real da empresa para conferir o formato. Até lá, lançamento manual
- [x] Sincronia diária (8h10) do **Portal da Transparência** (federal): empenho, liquidação, pagamento. Liga pelo número do processo (só dígitos, também quando vem na observação) e, sem processo, pela UG quando há uma licitação ganha só naquele órgão; o que não ligar fica "sem licitação" (`documentos-financeiros/sem-licitacao/` e `.../<id>/ligar/`). A sincronia do PNCP passa a guardar o `numero_processo` da compra. Conferida contra a API real em 07/11/2026 (chave aceita; nenhum empenho ainda)
- [x] Chave do Portal da Transparência na configuração do servidor (`PORTAL_TRANSPARENCIA_CHAVE` no `.env`; passo a passo no README do EC2)
- [ ] Prazo de validade da proposta (Lei 14.133, art. 90, §3º) e lembrete de cobrança por dias parados

### Passo 3 — Telegram
- [ ] Bot e configuração do chat; envio pelo Celery
- [ ] Avisos: convocação, diligência, pedido de desconto, recurso, empenho, pagamento, cobrança, prazo de desistência

### Passo 4 — Torre de Controle (frontend), ao lado da tela atual
- [x] Quadro com os 4 estágios lado a lado, etapa em cada cartão, mais urgente no topo (`/torre`)
- [x] Estágio aberto: etapas como colunas, barra com os 4 estágios no topo (`/torre/estagio/<estagio>`)
- [x] Menu novo: Buscar no topo, 13 etapas, Encerradas > Descartadas, Propostas (PDF), Cadastros
- [ ] No topo: Radar, status da Sentinela e sino de avisos (junto com a Sentinela beta)
- [x] Lista por etapa (`/torre/etapa/<etapa>`); Oportunidade e Cotação abrem as listas de hoje
- [x] Clique no cartão: Preparar abre o modal da oportunidade ou o Cotador; o resto abre a compra na plataforma

### Passo 5 — Sentinela v1.0 (extensão do Chrome)
- [ ] Caixa de mensagens do Compras.gov (sem captcha) a cada 3 min, 8h–18h
- [ ] Fases e situação por item a cada leitura da tela de participações (8h, 14h, 18h)
- [ ] Vigia: sessão caiu, verificação pedida, extensão parada
- [ ] Só alerta sobre itens em que a empresa tem proposta

## Referências

- Mapa etapa → fonte, com o que já foi confirmado: `estudo-de-caso-inside-solutions.md` (fora do repositório)
- Fluxograma das fases e protótipo da Torre: artefatos "Fases do Compras.gov" e "Licita v1.0"
- Códigos do Compras.gov: `comprasnet-fase-externa/v1/enums` (público)

## Depois do deploy

Para trazer as vitórias na hora, sem esperar as 8h do dia seguinte (no EC2):

```bash
cd /opt/licita && sudo docker compose exec backend python manage.py sincronizar_pncp
```

A API de Dados Abertos aceita no máximo 365 dias por consulta; o cliente
divide o período sozinho.

