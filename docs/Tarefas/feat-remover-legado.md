# feat/remover-legado — o que sai do produto

Proposta: https://claude.ai/artifact/G7q95215tZZDfe8WKttx3T (seção "Encaixe")

Três telas e um atalho de hoje não têm lugar no fluxo novo e saem. **Não são
substituídas aqui:** pesquisas salvas e Notificações são feats próprias. Este
arquivo só apaga o que já está morto, para o menu parar de mostrar tela que não
funciona.

**Decidido (20/09/2026):** Filtros e Alertas saem, o cotador antigo sai
inteiro, e a sala de disputa não herda nada dele.

**Decidido (21/09/2026):** oportunidade entra sempre **salva** — da busca só
se sai com "Salvar". O "Cotar" direto do card da busca sai; cotar é coisa de
dentro do processo.

## Tarefas

- [x] **1. Filtros — só frontend**
  Não existe backend: o frontend chama `/api/filtros/`, que não tem model nem
  rota em `backend/`. Saem `pages/filtros/`, `services/filtros/`,
  `contracts/filtros/`, `ENDPOINTS.filtros`, a rota `filtros` em
  `app.routes.ts` e o item do menu em `layout/sidebar/sidebar.component.ts`.
  O ícone `filtros` fica: `nav-item.component.spec.ts` o usa como exemplo. A
  busca automática não herda a tela — ela vira "Salvar pesquisa", dentro da
  própria Pesquisar.
  *Teste antes:* `sidebar.component.spec.ts` passa a esperar a lista de rótulos
  sem "Filtros"; a rota `/filtros` cai no curinga (vai para Pesquisar).

- [x] **2. Alertas (a tela de hoje) — só frontend**
  Mesmo caso: `/api/alertas/` não existe no backend. Saem `pages/alertas/`,
  `services/alertas/`, `contracts/alertas/`, `ENDPOINTS.alertas`, a rota e o
  item do menu. O ícone `alertas` fica para Notificações.
  *Teste antes:* rótulos do menu sem "Alertas"; `/alertas` cai no curinga.

- [x] **3. Cotador antigo — frontend**
  Saem `pages/cotador/` (a tela de `/cotador`, que é a antiga — o Cotador de
  verdade é `pages/oportunidades/cotador-modal/`),
  `services/licitacoes/cotacoes.service.ts`,
  `contracts/licitacoes/cotacao.contracts.ts`, a rota `cotador` e o item
  "Cotador" do menu. **Não confundir** com `contracts/cotador/` e
  `services/cotador/`, que são do Cotador novo e ficam. O ícone `cotador` sai
  se nada mais usar.
  *Teste antes:* rótulos do menu sem "Cotador"; o modal do Cotador novo continua
  abrindo da busca e das salvas.

- [x] **4. Cotador antigo — backend (a única parte que apaga dado)**
  Saem `licitacoes.Cotacao`, `apps/licitacoes/cotacao.py`,
  `apps/licitacoes/test_cotacao.py`, `CotacaoSerializer`,
  `OportunidadeSalvaCotacaoView` e sua rota em `apps/licitacoes/urls.py`. A
  migração remove a tabela `licitacoes_cotacao` — **as cotações feitas no
  cotador antigo em produção somem junto.** Antes de rodar em produção:
  contar as linhas e, se houver alguma que importe, exportar.
  *Contado em 26/09/2026:* uma linha só — um teste de 30/08 com total
  R$ 0,00 —, exportada para `/root/licitacoes_cotacao_antiga_backup.json` no
  servidor mesmo assim.
  *Teste antes:* a suíte de `licitacoes` passa sem `test_cotacao.py`; a
  migração aplica e reverte num banco limpo.

- [x] **5. Devolver o nome `cotacao` ao Cotador novo**
  `cotador.Cotacao.oportunidade` usa `related_name="cotacao_cotador"` só
  porque `cotacao` era do antigo (comentário em `apps/cotador/models.py`).
  Depois da tarefa 4, volta a ser `cotacao`, e a docstring de
  `apps/cotador/formulas.py` para de citar o cotador antigo.
  *Teste antes:* `oportunidade.cotacao` devolve a cotação do Cotador novo; os
  testes de `apps/cotador` passam sem mudança de comportamento.

- [x] **6. "Cotar" direto da busca sai**
  Hoje o card da Pesquisar tem "Cotar", e salvar essa cotação salva a
  oportunidade junto. Isso acaba: da busca, o edital só sai salvo.
  Frontend: o botão "Cotar" de `edital-card` (o output `cotar` e o input
  `podeCotar`, que hoje só existe para o modal das salvas desligá-lo),
  `pesquisar.page.ts::cotar()` e o `(cotar)` em `pesquisar.page.html`. No
  `cotador-modal`, o caminho que manda o payload `oportunidade` da busca e o
  aviso de `oportunidade_criada`.
  Backend: `apps/cotador/views.py::_resolver_oportunidade` passa a aceitar só
  `oportunidade_id`, e `oportunidade_criada` sai da resposta. As docstrings que
  dizem "salvar a cotação é o que salva a oportunidade" (`apps/cotador/models.py`
  e `views.py`) mudam junto. `salvas.garantir_salva` fica — é o salvar da busca.
  *Teste antes:* `POST /api/cotador/cotacoes/` com o payload `oportunidade`
  (sem `oportunidade_id`) é recusado com 400; o card da Pesquisar mostra só
  "Salvar"; o Cotador continua abrindo das salvas.

- [ ] **6. O quadro antigo do Ciclo de Licitação**
  A Torre de Controle o substituiu em 08/11/2026 (`docs/TORRE.md`). Hoje
  `/ciclo` e `/ciclo/visao-geral` já redirecionam para `/torre`; o código
  continua no repositório sem tela. Saem: `pages/ciclo/quadro/`,
  `services/licitacoes/ciclo.service.ts` (+ contrato), `CicloView` e a rota
  `GET ciclo/`, e `apps/licitacoes/ciclo.py` — **menos**
  `situacao_da_cotacao`, que o serializer de Cotação usa (mudar para
  `torre.py` ou `cotador`). Cotador, Propostas, Encerradas e Descartadas
  continuam em `pages/ciclo/` (são telas vivas: renomear a pasta é opcional).
  *Teste antes:* nenhum teste da Torre ou de `test_saidas.py` pode depender
  de `ciclo.py`; os testes do quadro antigo saem junto.

