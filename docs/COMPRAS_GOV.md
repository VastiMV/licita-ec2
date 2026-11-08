# Compras.gov.br — mapa de ações e endereços

Referência para quem mexe na Sentinela e na Torre. Tudo aqui saiu dos
**HARs gravados na sessão logada da Inside** (07–08/11/2026) e de testes **sem
login** feitos em 08/11/2026 (uma chamada por endereço). O Compras.gov não
publica esta API para fornecedores: **ela pode mudar sem aviso** — quando algo
parar de funcionar, grave um HAR novo e compare.

## Como ler a tabela

| Coluna | Significado |
|---|---|
| **Acesso** | 🌐 **abre direto** (sem login) · 🔐 **sessão** (precisa do fornecedor logado: sem ela o Compras.gov responde **403**) |
| **Captcha** | 🧩 **sim** — a página manda um código de **hCaptcha** novo em cada consulta (parâmetro `captcha=`). A Sentinela **nunca** gera nem resolve captcha: só copia o que a página recebeu quando a pessoa abriu a tela |
| **Sentinela** | 👁 **copia** (quando a pessoa abre a tela) · 🔁 **consulta sozinha** (só endereços sem captcha) · ✍ **escreve** (só com clique de alguém) · — não usa |

Base de todos os endereços: `https://cnetmobile.estaleiro.serpro.gov.br`.
`{compra}` = UASG (6) + modalidade (2) + número (5) + ano (4), ex.
`92667005000562026` (Pregão 56/2026, UASG 926670). `{cnpj}` = CNPJ só dígitos.
`{item}` = número do item ou do grupo (`22`, `G2`, `-4`). `{sessao}` = número
da sessão de julgamento (`numeroSessaoJulgHab`, quase sempre `1`).

## Sessão e reautenticação

- O login é pelo **gov.br**. Depois dele, a página manda em **toda** consulta
  o cabeçalho `authorization: Bearer <token>` (não é cookie), mais
  `x-device-platform: web` e `x-version-number: 6.4.4`.
- **A sessão vale por aba** (fica na memória/armazenamento da aba). Uma aba
  nova aberta "do zero" cai no login. Por isso o "Abrir" da Torre, com a
  Sentinela instalada, abre a compra numa **cópia** da aba já logada
  (Sentinela 0.1.3).
- **Renovação:** quando o token vence, a consulta volta **401**; a página
  chama `PUT /comprasnet-usuario/v2/sessao/fornecedor/retoken`, recebe
  `accessToken` + `refreshToken` novos e repete. **Se a renovação falhar, é
  login de novo** (gov.br). A Sentinela avisa: o botão do topo do Licita fica
  âmbar ("precisa de você").
- **O Compras.gov não avisa na tela** quando a sessão cai: a bolinha verde do
  topo não acompanha a sessão.
- **A página não se atualiza sozinha:** nenhuma consulta automática em 1
  minuto parado; só com clique no ↻.

## Leituras (GET)

| Ação na tela | Endereço | Acesso | Captcha | Sentinela |
|---|---|---|---|---|
| Lista de códigos (fases, situações…) | `/comprasnet-fase-externa/v1/enums` | 🌐 | não | — (consulta manual; tabelas em `torre.py`) |
| Lista de códigos da disputa | `/comprasnet-disputa/v1/enums` | 🌐 | não | — |
| Configuração de captcha | `/comprasnet-fase-externa/v1/captcha/configuracao` | 🌐 | não | — (diz `recaptchaHabilitado: false`; o captcha em uso é o **hCaptcha**) |
| Hora oficial de Brasília | `/comprasnet-disputa/v1/datahorabrasilia` | 🔐 | não | — |
| Quem está logado | `/comprasnet-usuario/v1/usuario` | 🔐 | não | — |
| **Minhas participações** (lista das compras) | `/comprasnet-fase-externa/v1/compras/participacoes?filtro&pagina&tamanhoPagina` | 🔐 | 🧩 **sim** | 👁 copia |
| Participação numa compra (fase, situação, prazos) | `/comprasnet-fase-externa/v1/compras/{compra}/participacao` | 🔐 | não | 👁 copia |
| Itens antes da sessão (traz a proposta da empresa **dentro** do item com preço) | `/comprasnet-fase-externa/v1/compras/{compra}/itens/aguardando-abertura-sessao-publica?pagina&tamanhoPagina` | 🔐 | 🧩 **sim** | 👁 copia (Sentinela 0.2) |
| Itens de um grupo, antes da sessão | `.../itens/aguardando-abertura-sessao-publica/{item}/itens-grupo` | 🔐 | não | 👁 copia (0.2) |
| **Itens da compra** depois da sessão — `filtro=1` "Todos os itens" (traz a proposta da empresa dentro do item) · `filtro=2` "Itens em que estou participando" · `filtro=3` "Itens com diligência" | `/comprasnet-fase-externa/v1/compras/{compra}/itens/em-selecao-fornecedores?filtro&pagina&tamanhoPagina` | 🔐 | 🧩 **sim** | 👁 copia (filtros 1 e 2) |
| Detalhes de um item | `/comprasnet-fase-externa/v1/compras/{compra}/itens/{item}/detalhamento` | 🔐 | não | — |
| **Minha proposta no item** (posição, valores, situação, **pedido de desconto**, convocação de anexo) | `/comprasnet-fase-externa/v1/compras/{compra}/em-selecao-fornecedores/participacoes/{cnpj}/itens/{item}/propostas?filtro` | 🔐 | não | 👁 copia · 🔁 consulta sozinha (0.2) |
| **Fase recursal do item** (prazos de intenção, recurso, **contrarrazões** e decisão; quem recorreu; texto das decisões) | `/comprasnet-fase-externa/v1/compras/{compra}/itens/{item}/fase-recursal-fornecedor/{sessao}` | 🔐 | não | 👁 copia · 🔁 consulta sozinha (0.2) |
| Um recurso (arquivo, data, intenção) | `.../itens/{item}/fase-recursal/{sessao}/recursos/{cnpj-de-quem-recorreu}` | 🔐 | não | — |
| Diligências da empresa no item | `/comprasnet-fase-externa/v1/compras/{compra}/itens/{item}/participacoes/{cnpj}/diligencias` | 🔐 | não | 👁 copia · 🔁 consulta sozinha (0.2) |
| Anexos da empresa no item | `/comprasnet-fase-externa/v1/compras/{compra}/itens/{item}/participacao/{cnpj}/anexos` | 🔐 | não | — |
| Itens para o filtro do chat | `/comprasnet-fase-externa/v1/sistema/compras/{compra}/mensagens/itens-para-filtro` | 🔐 | 🧩 **sim** | — |
| Tipos de mensagem para o filtro do chat | `/comprasnet-fase-externa/v1/sistema/compras/{compra}/mensagens/tipos-msg-para-filtro` | 🔐 | 🧩 **sim** | — |
| **Chat da compra** | `/comprasnet-mensagem/v2/chat/{compra}?page&size&legadoAsp` | 🔐 | 🧩 **sim, a cada consulta** | — (não usar) |
| **Chat do item** | `/comprasnet-mensagem/v2/chat/{compra}/itens/{item}?page&size&identificadorParticipante&incluirMensagensCompra` | 🔐 | 🧩 **sim, a cada consulta** | — (não usar) |
| **Caixa de mensagens do fornecedor** (todas as compras: convocação 830, pregoeiro 840, recurso 850, impugnação 810) | `/comprasnet-mensagem/v1/mensagens?page&size&dataHoraMenorQue&tagsSelecionadas` | 🔐 | não | planejado: 🔁 consulta sozinha |
| Contador de não lidas | `/comprasnet-mensagem/v1/mensagens/quantidade-nao-lidas` | 🔐 | não | planejado |
| Abrir uma mensagem (**marca como lida**) | `/comprasnet-mensagem/v1/mensagens/{id}` | 🔐 | não | — (nunca: marcaria como lida) |
| Notificações do sino do Compras.gov | `/comprasnet-mensagem/v1/destinatarios/notificacoes` | 🔐 | não | — |
| Quais compras estão favoritadas | `/comprasnet-oportunidade/v1/compras/favoritas/dentre-opcoes?compras=…` | 🔐 | não | — |
| Quais itens estão favoritados | `/comprasnet-oportunidade/v1/compras/{compra}/itens/favoritos?itens=…` | 🔐 | não | — |

## Escritas

| Ação na tela | Endereço | Acesso | Captcha | Sentinela |
|---|---|---|---|---|
| Renovar a sessão | `PUT /comprasnet-usuario/v2/sessao/fornecedor/retoken` | 🔐 | não | — (é a página que faz; a Sentinela só percebe quando falha) |
| **Favoritar** a compra | `POST /comprasnet-oportunidade/v1/compras/{compra}/favorita` (sem corpo; cabeçalho `bloqueio-desabilitado: true`) | 🔐 | não | — |
| **Tirar o favorito** da compra | `DELETE /comprasnet-oportunidade/v1/compras/{compra}/favorita` (idem) | 🔐 | não | ✍ só pela **lixeira** do Licita, com o clique de alguém (Sentinela 0.2, em espera) |

Tirar o favorito **não retira proposta**: com preço lançado, a compra continua
em "Minhas participações".

## Páginas (o que a pessoa abre no navegador)

| Página | Endereço | Acesso |
|---|---|---|
| Área de trabalho do fornecedor (depois do login) | `https://www.comprasnet.gov.br/…` (o portal antigo) | 🔐 |
| Compras eletrônicas — Minhas participações / Todas as compras | `/comprasnet-web/seguro/fornecedor/compras` | 🔐 |
| **Acompanhamento da compra (do fornecedor)** — "Minha proposta", filtros de itens, chat, fase recursal | `/comprasnet-web/seguro/fornecedor/acompanhamento-compra?compra={compra}` | 🔐 — **é o "Abrir" da Torre** |
| Acompanhamento **público** da compra (qualquer pessoa) | `/comprasnet-web/public/compras/acompanhamento-compra?compra={compra}` | 🌐 — sem proposta, sem filtros da empresa; usado só na **busca** do Licita |

## Fora do Compras.gov (fontes sem sessão)

| Fonte | Endereço | Acesso | Uso no Licita |
|---|---|---|---|
| Dados Abertos do Compras.gov (resultados e atas por fornecedor) | `https://dadosabertos.compras.gov.br/modulo-contratacoes/3_consultarResultadoItensContratacoes_PNCP_14133`, `/modulo-arp/2_consultarARPItem` | 🌐 (máx. 365 dias por consulta) | sincronia do PNCP, dias úteis às 8h |
| Portal da Transparência (empenho, liquidação, pagamento) | `https://api.portaldatransparencia.gov.br/api-de-dados/despesas/documentos-por-favorecido` | 🔑 chave `chave-api-dados` (`PORTAL_TRANSPARENCIA_CHAVE`) | sincronia, dias úteis às 8h10 |
| PNCP (busca de editais) | `https://pncp.gov.br/api/...` | 🌐 | busca de oportunidades |

## API do Licita para a Sentinela

Todas em `https://insidelicitacoes.com.br/api/sentinela/` (sem `www`: o
`www.` redireciona e o POST vira GET → 405). Autenticação: cabeçalho
`X-Sentinela-Chave` = `SENTINELA_CHAVE` do servidor.

| Endereço | Para quê | Versão |
|---|---|---|
| `POST pulso/` | sinal de vida (estado da Sentinela) | 0.1 |
| `POST captura/` | `{url, dados}`: a resposta que a página recebeu; o Licita interpreta (`apps/sentinela/ingestao.py`) | 0.1 |
| `GET camada/{compra}/` | números da camada de disputa (teto, ideal, piso, custo, lucro) | 0.1 |
| `GET estado/` | para o botão do topo do Licita (usuário logado, não a chave) | 0.1 |
| `GET tarefas/`, `POST tarefas/{id}/` | tarefas pedidas pelo Licita (tirar favorito) | 0.2 (em espera) |
| `GET ronda/` | o que consultar sozinha (proposta, recurso, diligências) | 0.2 (em espera) |

## Regras que não se negociam

1. **Nunca gerar, resolver ou contornar captcha.** Tela com 🧩 só é lida
   quando a pessoa a abre.
2. **Nunca guardar senha nem token.** A sessão é usada só na memória da aba,
   do mesmo jeito que a página usa.
3. **Escrita só com clique de alguém**, uma compra por vez (hoje: tirar o
   favorito pela lixeira).
4. **Nunca abrir mensagem** pela API (marca como lida).
5. **Ritmo de gente:** consultas uma por vez, com pausa; nada de rajada.
