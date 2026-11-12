# Licita

Plataforma da **Inside Solutions** para encontrar, cotar e acompanhar
licitações públicas (Lei 14.133), integrando com o PNCP e o compras.gov.br.
A equipe busca oportunidades, salva as que interessam, monta a cotação
(Cotador) e acompanha cada uma pela **Torre de Controle** — da oportunidade
até o pagamento.

> **Chegou agora para mexer no sistema?** Leia nesta ordem:
> 1. este README (o que é, onde roda, como trabalhar);
> 2. [`docs/TORRE.md`](docs/TORRE.md) — a Torre de Controle, o coração do
>    sistema: etapas, de onde vem cada dado, em que arquivo está cada regra;
> 3. [`docs/DOMINIO.md`](docs/DOMINIO.md) — as outras regras de negócio (o "porquê");
> 4. [`docs/ARQUITETURA.md`](docs/ARQUITETURA.md) — como o código se organiza;
> 5. [`deploy/ec2/README.md`](deploy/ec2/README.md) — o servidor, os botões
>    de deploy e de teste, o backup e como voltar um deploy;
> 6. [`docs/Tarefas/feat-torre-de-controle.md`](docs/Tarefas/feat-torre-de-controle.md)
>    — **onde paramos** e o que vem depois.

## Dois repositórios

| Repositório | O que é | Onde roda |
|---|---|---|
| **`VastiMV/licita-ec2`** (este) | a versão **em produção** da Inside Solutions | EC2 próprio na AWS (`docker compose`) |
| `VastiMV/licita` | o original, de onde este foi copiado em 06/11/2026 | cluster Kubernetes (servidor de terceiro) |

Os dois **não se atualizam sozinhos**: uma mudança feita num não aparece no
outro. O trabalho do dia a dia é feito **aqui**.

## Onde está no ar

| Ambiente | Endereço | Roda |
|---|---|---|
| **Produção** | `https://insidelicitacoes.com.br` (no ar; o `www.` redireciona para ele) | a branch `main` |
| **Teste** | `https://teste.<IP com hífens>.sslip.io` (o IP está no segredo `EC2_HOST`) | a branch que estiver em teste (liga e desliga sob demanda) |

Os dois rodam na mesma máquina (EC2 `licita`, região us-east-2, IP fixo —
não fica no repositório: segredo `EC2_HOST`), com bancos **separados**. Detalhes, senhas (onde ficam) e
como recriar a máquina: [`deploy/ec2/README.md`](deploy/ec2/README.md).

## Como trabalhar (o fluxo de toda mudança)

**A `main` é o que está no ar. Ninguém mexe direto nela.** Toda mudança:

1. **Branch nova** a partir da `main` — **um assunto por branch** (ex.: o
   logo e a regra de Descartadas foram branches separadas). Nome com o
   **código do cartão** do Jira: `GEN-48-descricao`; o título do PR começa
   com `GEN-48:`. Regras para agentes de IA: [`AGENTS.md`](AGENTS.md).
2. **Código + testes** (teste vem antes do código — ver "Estratégia de
   testes" em `docs/ARQUITETURA.md`). Rodar as duas suítes localmente:
   `backend/README.md` e `frontend/README.md`.
3. **Testar no ar:** GitHub → Actions → **Teste: ligar** → em "Use workflow
   from" escolha a branch. Abre em `teste.<domínio>`. Ajustes vão na
   **mesma branch** (enquanto não houve merge) e o botão roda de novo.
4. **Pull request** para a `main`, com o que mudou e o resultado dos testes.
5. **Merge** (squash) — só com o "sim" de quem pediu a mudança.
6. **Deploy:** Actions → **Deploy EC2** (com "Gerar imagens novas" marcado
   quando o código mudou). Só aí vai para a produção.
7. **Teste: desligar** quando terminar (o teste divide a memória com a
   produção).

Depois do merge a branch está encerrada: correção posterior é **branch nova**.
Documentação (como esta) não precisa de teste nem de deploy.

**Antes de qualquer deploy:**

- **Nunca em dia ou hora de sessão pública** (o Carlinhos pode estar dando
  lance). Pergunte. Noite e fim de semana são seguros.
- O deploy faz **backup do banco sozinho** antes de mexer (`atualizar.sh`).
  Deu errado? `deploy/ec2/README.md`, "Voltar um deploy que deu errado".
- Exceção registrada: a Torre de Controle (08/11/2026) foi direto para a
  produção, sem passar pelo Teste e sem pull request, por decisão da dona
  (o banco estava quase vazio e o sistema antigo segue em outra instância).
  Não é o fluxo normal.

## Stack

| Camada | Tecnologia |
|---|---|
| Backend / API | Django 6 + Django REST Framework, servido por Daphne (ASGI) |
| Frontend web | Angular 22 (standalone, zoneless) |
| Assíncrono | Celery (worker + beat) + RabbitMQ |
| Banco de dados | PostgreSQL 16 |
| Produção | 1 EC2 com `docker compose` + Caddy (HTTPS automático) — [`deploy/ec2/`](deploy/ec2/) |
| Imagens | GitHub Actions → `ghcr.io/vastimv/licita-ec2-{backend,frontend}` |
| Alternativa | manifests Kubernetes em [`k8s/`](k8s/) (usados pelo repositório original) |

## O que existe hoje

**A tela inicial é a Torre de Controle** (`/torre`). Depois do login, é ela
que abre.

**Telas (menu, de cima para baixo):**

| Menu | Tela | O que faz |
|---|---|---|
| Buscar oportunidades | busca | busca ao vivo no PNCP/compras.gov.br, por palavra-chave ou UASG |
| Torre de Controle | quadro | os 4 estágios lado a lado (Preparar, Disputar, Contratar, Receber), um cartão por licitação na etapa em que ela está — ver [`docs/TORRE.md`](docs/TORRE.md) |
| Preparar › Oportunidade | Salvas | a lista da equipe — só o que ainda está no prazo |
| Preparar › Cotação | Cotador | formação de preço por item, com comparação de fornecedores; exporta .xlsx |
| Preparar, Disputar, Contratar, Receber › (cada etapa) | lista da etapa | as licitações naquela etapa agora, com o número ao lado no menu |
| Encerradas | lista | quem **participou** e saiu (perdeu, revogada, anulada, fracassada, deserta) e as que ele só **acompanha** para ver o resultado ("xeretar") — cada uma com **relatório** (quem ganhou, marca, valor, diferença) |
| Encerradas › Descartadas | lista | quem saiu **antes** de participar (tirada da lista, prazo vencido, sem proposta cadastrada) |
| Propostas (PDF) | lista | a proposta comercial ajustada, pedida depois de ganhar (Word + arquivos) |
| Relatórios › Mês a mês | relatório | por mês: participou, ganhou, perdeu, faturamento e lucro (com cotação); "perdeu por pouco" (até 5%); **o mercado de cada item** (preço médio do item exato do catálogo em 3/6/12/24 meses, marcas que mais vencem, quanto ele ofereceu) |
| Cadastros | Empresas, Fornecedores, Produtos | os CNPJs com que a equipe disputa (e o dossiê de habilitação); de quem compra; Fabricante › Marca › Modelo |
| Configurações | Armazenamento, Usuários | só administrador |

**No topo da tela:** a empresa e o CNPJ, o **Radar** (em breve), o estado da
**Sentinela** (verde lendo, âmbar precisa de você, vermelho parada) e o
**sino** 🔔: convocação, pedido de desconto, recurso, mensagens do Compras.gov,
data alterada, compra suspensa, fora dos favoritos, resultados. **Os mesmos
avisos vão para o Telegram** de quem estiver cadastrado (botão "Testar
Telegram" no painel do sino; configuração em `deploy/ec2/README.md`).

**Sentinela (0.2.6, 12/11/2026):** extensão do Chrome no computador do
Carlinhos ([`sentinela/`](sentinela/), guia em
[`sentinela/README.md`](sentinela/README.md)). Traz para a Torre as compras e
os itens em que ele participa no Compras.gov, mostra a **camada de disputa**
(teto, ideal, piso, custo, lucro) ao lado da tela e, a cada 10 minutos, faz a
**ronda** sozinha (só telas sem captcha): caixa de mensagens, favoritos,
proposta/recurso/diligência dos itens, propostas de todos os participantes
(👍/🟠/👎) e a **vigia diária** dos itens perdidos até a ata do concorrente. Plano e limites:
[`docs/SENTINELA.md`](docs/SENTINELA.md). Todos os endereços do Compras.gov (login,
captcha, o que abre direto): [`docs/COMPRAS_GOV.md`](docs/COMPRAS_GOV.md).

**Sozinho, de segunda a sexta** (Celery Beat): às **7h45** a **conferência
diária** (data e situação das licitações em Preparar no PNCP, itens das
compras acompanhadas, fim da vigia por ata assinada, mercado de cada item);
às 8h o **PNCP** traz o que a empresa ganhou e as atas; às 8h10 o **Portal da
Transparência** traz empenho, liquidação e pagamento dos órgãos federais.

**Conferência pelo assistente, só leitura:** botão **Consultar EC2** no
GitHub Actions (`diagnostico`: itens-suspeitos, compra, torre, sentinela,
quedas, telegram) e a chave de leitura `LEITURA_CHAVE` (só GET) — ver
`deploy/ec2/README.md`.

As regras de cada uma estão em [`docs/TORRE.md`](docs/TORRE.md) e
[`docs/DOMINIO.md`](docs/DOMINIO.md).

**Ainda não existe** (em ordem de prioridade): fim da vigia por **contrato**
publicado no PNCP (hoje: ata de registro de preços ou 180 dias), tirar o
**Ciclo de Licitação** antigo do código, o painel da camada mostrar só o item
aberto e o aviso de lance abaixo do piso (precisam de um .har da tela de
lances), o **Radar** e as telas para **lançar à mão** contrato, ordem de
fornecimento e entrega (a API já existe). Lista viva:
[`docs/Tarefas/proximo-build.md`](docs/Tarefas/proximo-build.md).

## Estrutura do repositório

```
backend/         Django/DRF — ver backend/README.md
frontend/        Angular — ver frontend/README.md
sentinela/       a extensão do Chrome (Sentinela) — ver sentinela/README.md
deploy/ec2/      produção no EC2: docker compose, Caddy, scripts e o guia
k8s/             manifests Kubernetes (alternativa; usados no repositório original)
docs/            TORRE.md, SENTINELA.md, COMPRAS_GOV.md, DOMINIO.md, ARQUITETURA.md, Tarefas/, mockups e atas
.github/workflows/
  build-image.yml      gera as imagens (chamado pelos outros dois)
  deploy-ec2.yml       botão "Deploy EC2" — produção
  teste-ligar.yml      botão "Teste: ligar" — ambiente de teste
  teste-desligar.yml   botão "Teste: desligar"
  consultar-ec2.yml    botão "Consultar EC2" — conferência só leitura
  docs-imagem.yml      botão "Documentação: gerar imagem" — o site da documentação
```

**Documentação navegável:** `https://insidelicitacoes.com.br/documentacao`
(menu **Documentação**, mesmo login). Fonte: `docs/` + `mkdocs.yml`.
