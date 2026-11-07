# Tarefas

Uma lista por *feat*, na ordem em que uma depende da outra. Cada arquivo tem
as tarefas com o que entrega, o teste que vem antes e os arquivos tocados —
marcar `[x]` ao concluir, no mesmo commit que fecha a tarefa.

O "o que fazer" de cada módulo está nas propostas (artefatos), linkadas em
cada arquivo. Aqui é só o "como", quebrado em pedaço entregável.

| Feat | O que é | Depende de |
|---|---|---|
| [`armazenamento`](feat-armazenamento.md) | Onde qualquer arquivo do produto é gravado — bucket escolhido e configurado pelo cliente na tela, como plugin | — |
| [`cadastro-empresa`](feat-cadastro-empresa.md) | Os CNPJs com que a equipe disputa, e **os documentos da empresa** (certidões, contrato social, balanço) | `armazenamento` |
| [`documentos-processo`](feat-documentos-processo.md) | **Os documentos da licitação** — a pasta que nasce ao salvar a oportunidade e se enche sozinha ao longo do processo | `armazenamento`, `cadastro-empresa` |
| [`proposta`](feat-proposta.md) | A proposta comercial em si (ainda sem desenho de produto) | `documentos-processo` |
| [`remover-legado`](feat-remover-legado.md) | O que sai do produto: Filtros, a tela de Alertas de hoje, o cotador antigo e o "Cotar" direto da busca | — |
| [`usuario`](feat-usuario.md) | Configurações → Usuários: quem acessa, e o super usuário como o único que vê Configurações | — |
| [`produtos`](feat-produtos.md) | Cadastros › Produtos: Fabricante › Marca › Modelo, afinidade com fornecedor e tabela de preços no Cotador | — |
| [`torre-de-controle`](feat-torre-de-controle.md) | O ciclo inteiro da licitação, da oportunidade ao pagamento: 4 estágios, 13 etapas, PNCP, Portal da Transparência, Telegram e Sentinela | `proposta`, `produtos` |

## As duas famílias de documento

São coisas diferentes e não compartilham model — só o armazenamento:

- **Documento da empresa** é uma *vaga fixa*: a lista de tipos vem da Lei
  14.133 e é sempre a mesma; o que muda é a validade, e renovar cria uma
  versão nova na mesma vaga. Mora em `apps/documentos`.
- **Documento da licitação** é um *arquivo de uma fase*: não há lista fixa,
  não há validade, e o mesmo processo pode ter três catálogos de fornecedor e
  nenhum atestado. Mora junto da oportunidade, em `apps/licitacoes`.

O que os dois usam igual é `apps/armazenamento`: gravar, abrir, gerar link
temporário, remover — sem saber de qual bucket se trata.
