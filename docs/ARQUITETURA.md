# Arquitetura

Stack construída sobre um cluster Kubernetes. Domínio de negócio em
[`DOMINIO.md`](DOMINIO.md).

## Visão geral

```
                         ┌───────────────┐
        internet ───────►│   Ingress     │
                         └──────┬────────┘
                    ┌───────────┴────────────┐
                    ▼                        ▼
           ┌─────────────────┐      ┌──────────────────┐
           │  frontend (svc) │      │  backend (svc)    │
           │  Angular (nginx)│      │  Django + DRF      │
           └─────────────────┘      └────────┬──────────┘
                                              │
                          ┌───────────────────┼────────────────────┐
                          ▼                   ▼                    ▼
                 ┌────────────────┐  ┌─────────────────┐  ┌────────────────┐
                 │ postgres (sts) │  │ rabbitmq (svc)   │  │ celery-worker   │
                 │ PVC            │  │                  │  │ celery-beat     │
                 └────────────────┘  └────────┬─────────┘  └────────┬────────┘
                                               └─────────────────────┘
                                          (worker/beat consomem do broker)
```

Namespace único por enquanto: `inside-solutions-licita` (ver `k8s/namespace.yaml` —
manifests já usam esse nome; o valor `licita` que aparecia aqui antes nunca foi o real).

## Framework

- **Backend:** Django (última versão estável) como API via Django REST
  Framework. Sem views server-side renderizadas — só JSON.
- **Frontend:** Angular (última versão estável), consumidor web da API.
  Servido como estático (build de produção) atrás de nginx no próprio pod.
- **Mobile (futuro):** Flutter, ou outro framework nativo/híbrido, consumindo
  a mesma API DRF. Não implica mudança no backend — é só mais um client.

### Backend — organização em apps Django

| App | Responsabilidade |
|---|---|
| `accounts` | usuários, autenticação (JWT), perfil |
| `catalogo` | model `Pdm`, sincronização do catálogo de materiais |
| `licitacoes` | busca de oportunidades (live, cruza PNCP + catálogo), os models `OportunidadeSalva`/`EventoOportunidadeSalva` (lista salva + histórico) e a **Torre de Controle**: `torre.py` (etapas), `encerradas.py` (saídas), os models `ParticipacaoCompra`/`ItemParticipado`/`DocumentoFinanceiro`/`Entrega` e as sincronias diárias `sincronia_pncp.py`/`sincronia_transparencia.py` — ver [`TORRE.md`](TORRE.md) |
| `tenants` | model `Tenant` (uma linha só hoje) e `tenant_atual()`, o único ponto que resolve de quem é a requisição — ver `DOMINIO.md` |
| `empresas` | model `Empresa` — os CNPJs com que a equipe disputa (não confundir com `fornecedores`, que é de quem ela compra) |
| `documentos` | dossiê de habilitação da empresa: catálogo da Lei 14.133, a vaga de cada documento, as versões com validade e o histórico — ver `DOMINIO.md` |
| `fornecedores` | model `Fornecedor` — o cadastro compartilhado de quem a empresa compra para revender; é a base que o Cotador amarra a cada item |
| `produtos` | Fabricante › Marca › Modelo, a afinidade fornecedor↔fabricante e a tabela de preços (`PrecoFornecedor`) que o Cotador alimenta |
| `propostas` | a etapa depois do Cotador: a proposta em Word (modelo do cliente), os documentos de habilitação conferidos e os arquivos da licitação |
| `capag` | nota CAPAG (Tesouro) de municípios e estados — o selo do card |
| `cotador` | formação de preço de uma oportunidade (`Cotacao`/`ItemCotacao`/`OfertaFornecedor`), a conta em `formulas.py` e a proposta em .xlsx (`planilha.py`). App próprio, e não um campo novo no cotador antigo de `licitacoes`: os dois respondem perguntas diferentes e os nomes de campo colidiriam — ver a docstring de `apps/cotador/models.py` |
| `filtros`, `alertas` | **saíram do plano** (`feat-remover-legado`, 20/09/2026). O aviso ao usuário passa a ser o sino do Licita e o Telegram, alimentados pela Sentinela e pelas sincronias — ver `TORRE.md` |
| `integracoes` | clients HTTP para PNCP, compras.gov.br (inclusive Dados Abertos: resultados e atas por fornecedor) e Portal da Transparência (`clients/transparencia.py`), isolados do resto (mockáveis nos testes) |
| `armazenamento` | onde os arquivos ficam — interface única, drivers registráveis (Cloudflare R2, AWS S3, disco local) e a configuração que o cliente edita na tela; ver a seção "Armazenamento de arquivos" |
| `config/` (não é app) | settings (`environment.py` é a única porta para variável de ambiente), ASGI, Celery e rotas |

### Frontend — organização Angular

- Standalone components (padrão atual do Angular), lazy-loaded por feature,
  em `pages/`: `torre/` (a tela inicial: quadro, estágio aberto, lista por
  etapa e o cartão — ver [`TORRE.md`](TORRE.md), seção 9), `oportunidades/`
  (busca e salvas), `ciclo/` (Cotador, Propostas, Encerradas, Descartadas),
  `empresas/`, `fornecedores/`, `produtos/`, `configuracoes/`, `auth/`.
- `layout/`: o menu (`sidebar/`, com a contagem por etapa), o topo
  (`navbar/` + `topo-status/`: empresa, Radar, Sentinela, sino) e o `shell/`.
- Cores, espaçamentos e letra só em `src/styles/_tokens.scss` (nenhum
  componente declara cor solta). O visual segue o protótipo "Licita v1.0".
- Um `ApiService`/`HttpInterceptor` central cuida do token JWT e do refresh.
- Consome só a API DRF — nenhuma lógica de negócio (matching de filtro,
  parsing de catálogo) duplicada no frontend.

## Autenticação

Angular é client puro da API DRF — não há sessão server-side compartilhada, o
que combina com o requisito de pods efêmeros/escaláveis. Mecanismo:
`djangorestframework-simplejwt` (access + refresh token).

### Fluxo

1. `POST /api/auth/login/` — recebe `email`/senha, devolve `access` (curta
   duração, ~5–15 min) no corpo da resposta e seta o `refresh` (~7 dias) como
   cookie `httpOnly`, `Secure`, `SameSite=Lax`.
2. Angular guarda o `access` **em memória** (campo privado do `AuthService`),
   nunca em `localStorage`/`sessionStorage` — reduz o que um XSS consegue
   roubar de forma persistente.
3. `HttpInterceptor` injeta `Authorization: Bearer <access>` em toda chamada
   à API.
4. Request que volta `401` dispara `POST /api/auth/refresh/` (o cookie
   `httpOnly` vai junto automaticamente, sem o JS tocar nele); o interceptor
   trava chamadas concorrentes de refresh para não disparar várias em
   paralelo, aplica o `access` novo e repete o request original.
5. `POST /api/auth/logout/` invalida o `refresh` (blacklist do
   `simplejwt`) e o Angular descarta o `access` da memória.
6. Rotas protegidas usam `canActivate` (functional guard) checando se há
   `access` válido em memória; sem ele, redireciona para `/login`.

### Implicações de infraestrutura

- Cookie `httpOnly` exige `withCredentials: true` no Angular e
  `CORS_ALLOW_CREDENTIALS = True` + `CORS_ALLOWED_ORIGINS` explícito no
  Django (nunca `*` quando `credentials` está ligado).
- `/api/auth/refresh/` fica sujeito a CSRF (é o único endpoint de auth que
  depende de cookie); os demais usam só o header `Authorization` e não
  precisam de CSRF token.
- `Filtro` (ver [`DOMINIO.md`](DOMINIO.md)) ganha `owner = FK User`; todo
  `ViewSet` de `filtros`/`alertas` usa `permission_classes = [IsAuthenticated]`
  e filtra o queryset por `request.user`.
- Sessão de admin do Django continua disponível em `/admin/` (cookie de
  sessão padrão), só para operação interna — não é o mecanismo usado pelos
  clients.

## Pods

Um pod por responsabilidade, todos **stateless e efêmeros** (nada em disco
local que não seja regenerável), para escala horizontal sem coordenação:

| Deployment | Réplicas iniciais | Escala horizontal |
|---|---|---|
| `frontend` | 1 | sim — estático, sem estado |
| `backend` | 1 | sim — sem sessão em memória; auth é JWT |
| `sincronizador-catalogo-pdm`¹ | 1 | sim — várias réplicas concorrem na mesma fila |
| `celery-beat` | 1 | **não** — agendador é singleton por definição; nunca escalar além de 1 réplica |

¹ Nome do Deployment de worker Celery — nomeado pela task que roda hoje
(`catalogo.sincronizar_catalogo_pdm`, única existente), não "celery-worker"
genérico. Ver comentário em
`k8s/backend/sincronizador-catalogo-pdm-deployment.yaml` para o que fazer
quando `verificar_filtros_ativos`/`enviar_email_alerta` (tabela abaixo)
ganharem workers — decidir então entre renomear de volta pra genérico ou
rotear por fila dedicada.

`postgres` e `rabbitmq` não são `Deployment`: `postgres` é `StatefulSet` (ver
abaixo); `rabbitmq` roda como `StatefulSet` de 1 réplica nesta fase (fila
única, sem cluster) — reavaliar cluster de 3 nós só se o volume justificar.

### Assíncrono — Celery + RabbitMQ

Tudo que depende de rede externa ou é demorado sai do request/response e vira
task Celery, com RabbitMQ como broker:

| Task | Gatilho | Frequência |
|---|---|---|
| `sincronizar_catalogo_pdm` | Celery Beat | diária (ou sob demanda via endpoint admin) |
| `licitacoes.sincronizar_pncp` | Celery Beat | segunda a sexta, 8h (Brasília) — vitórias e atas da empresa; ver `TORRE.md` |
| `licitacoes.sincronizar_transparencia` | Celery Beat | segunda a sexta, 8h10 — empenho, liquidação, pagamento federais |
| chamadas à API do PNCP/compras.gov.br feitas por busca interativa do usuário | request síncrono da `licitacoes` view | -- ficam síncronas mesmo, são a resposta da busca; só o que não bloqueia a resposta ao usuário vira task |

Agendamento via `django-celery-beat` (schedule editável no banco/admin, não
hardcoded), substituindo o `APScheduler` embutido do protótipo — que não
sobrevive a múltiplas réplicas do pod da API.

## Banco de dados

- **PostgreSQL**, um banco por enquanto, no mesmo namespace do resto.
- Roda como **`StatefulSet`** (identidade estável de pod + volume, ao
  contrário de `Deployment`), 1 réplica nesta fase — réplica de leitura fica
  para quando houver necessidade real.
- **PVC escrito manualmente** (não dinâmico via `StorageClass` default),
  para controle explícito de tamanho, política de retenção
  (`persistentVolumeReclaimPolicy: Retain`) e localização do volume.
- **`StorageClass` dedicada**, para que o volume dos dados seja fácil de
  localizar e intervir manualmente (backup, migração) — parâmetros exatos
  (provisioner, zona) dependem de qual cluster/cloud hospeda o Kubernetes;
  a definir quando essa informação existir.
- Credenciais via `Secret` (`POSTGRES_USER`, `POSTGRES_PASSWORD`,
  `POSTGRES_DB`), nunca em `ConfigMap`.

## Armazenamento de arquivos

Documentos da empresa, edital baixado do PNCP, planilha do Cotador: tudo que
é arquivo passa por `apps/armazenamento`, e **nada no resto do projeto sabe
que existe S3**. Quem grava chama quatro métodos — `salvar`, `abrir`,
`url_temporaria`, `remover` — e qual serviço responde é decisão de
configuração.

### Por que é plugin

Um driver se registra no `ready()` do app dele (`registrar(Classe)`), e
**declara os campos que precisa** (`CAMPOS`). Isso tem duas consequências que
valem a indireção:

1. **Trocar de provedor não é deploy.** Cloudflare R2, AWS S3, MinIO e Spaces
   falam o mesmo protocolo — muda `endpoint_url` e região. Por isso não há um
   driver por fornecedor: há `drivers/s3.py`, registrado como `r2` e `s3`.
2. **A tela se desenha sozinha.** O frontend não conhece R2: ele pede
   `GET /api/armazenamento/drivers/`, recebe a lista de campos e monta o
   formulário. Um driver novo, instalado como pacote no backend, aparece na
   tela sem uma linha de Angular.

O driver `local` (disco) existe para o desenvolvimento e **para os testes**:
nenhum teste do projeto fala com bucket de verdade, pela mesma disciplina de
`integracoes`, que nunca faz rede em teste.

### Por que a configuração é registro de banco

`ConfigArmazenamento` (um por tenant) guarda driver, opções e segredos. Não é
`ConfigMap`/`Secret` porque precisa ser **por cliente** e **mudável pela tela
sem redeploy** — que é o pedido. Em troca, uma credencial de bucket passa a
morar no Postgres, então:

- o segredo é **cifrado** (Fernet) e nunca volta pela API — a tela recebe
  "definido em tal data" e só envia valor novo se alguém digitar;
- a chave da cifra — **e só ela** — vem do ambiente
  (`ARMAZENAMENTO_CHAVE_CIFRA`, no `backend-secrets`): é a única coisa que não
  pode estar junto do dado que protege. Driver, bucket, endpoint e credencial
  ficam todos no banco, na configuração do plugin daquele tenant;
- "Testar conexão" grava um byte, lê de volta e apaga, para credencial errada
  aparecer ali e não no primeiro upload.

Só `is_staff` configura (`IsAdminUser`), enquanto o produto não tiver papéis
de acesso.

### Caminho e download

A chave é `tenant/<slug>/...` desde o primeiro arquivo, mesmo com um cliente
só: um bucket com prefixo por tenant atende os dois mundos, e quem preferir
bucket separado por cliente só preenche outro bucket. Começar sem prefixo e
querer separar depois é mover arquivo, não mudar código.

**O bucket nunca é público.** O download é sempre URL assinada de curta
duração — certidão tem CNPJ, endereço e nome de sócio. O upload passa pelo
backend enquanto o teto for 50 MB (valida tipo, calcula hash, grava o
evento); quando houver arquivo grande, o mesmo driver emite URL de envio
direto e a interface não muda.

## Configuração e segredos

| Recurso | Conteúdo |
|---|---|
| `ConfigMap` `backend-config` | `DJANGO_SETTINGS_MODULE`, URLs internas de serviço, feature flags |
| `Secret` `backend-secrets` | `SECRET_KEY`, credenciais do Postgres, credenciais RabbitMQ, credenciais do provedor de e-mail, `ARMAZENAMENTO_CHAVE_CIFRA` (cifra dos segredos de `apps/armazenamento`) |
| `Secret` `postgres-secrets` | usuário/senha do banco |

## Estratégia de testes

**Nenhum código de funcionalidade entra sem teste antes dele.** Isso vale
para todo item de "Próximos passos" abaixo: os testes que especificam o
comportamento são escritos e revisados antes de escrever a implementação —
não depois, "para cobrir". Um PR que só adiciona teste depois do código é
retrabalho, não é o processo.

Ferramental é o padrão nativo de cada framework — sem introduzir runner
alternativo por preferência pessoal:

### Por camada

| Camada | Ferramenta | Escopo mínimo |
|---|---|---|
| Backend (models, serializers, regras) | `django.test.TestCase` (test runner padrão do Django, via `manage.py test`) | toda regra de `docs/DOMINIO.md` (matching de filtro, fallback catálogo↔PNCP, geração de `Alerta`) tem teste antes de existir código |
| Backend (endpoints DRF) | `rest_framework.test.APITestCase` (extensão do `TestCase` padrão, já pensada para DRF) | autenticação (login, refresh, 401 sem token, logout invalida refresh), permissão (dono só vê seu próprio `Filtro`), contrato de cada endpoint |
| Clients de integração (`integracoes/`) | `TestCase` + `unittest.mock`/`requests-mock` | **sem rede real nos testes** — mesma disciplina do protótipo (`tests/conftest.py` já desligava a busca do PNCP por padrão); contrato mockado a partir do `api-spec.json` e dos comportamentos documentados em `DOMINIO.md` (paginação 10–500, `/api/search/` etc.) |
| Tasks Celery | `TestCase` com `CELERY_TASK_ALWAYS_EAGER=True` | `sincronizar_catalogo_pdm`, `sincronizar_pncp`, `sincronizar_transparencia` rodam síncronas no teste, sem broker nem rede real (clients falsos com o formato real das APIs) |
| Frontend (Angular) | Vitest via `ng test` (`*.spec.ts` ao lado de cada arquivo) | `AuthService`/interceptor (refresh automático, fila de requests em 401, logout limpa estado), guards de rota, telas da Torre, menu e topo |
| Frontend (fluxo ponta a ponta) | a definir (Playwright é o candidato natural — não tem padrão nativo do Angular CLI para e2e desde a remoção do Protractor) | login → criar filtro → alerta aparece — pelo menos o caminho feliz, antes de considerar uma feature "pronta" |

### CI

Pipeline bloqueia merge se os testes não passarem — a definir plataforma
(GitHub Actions é o candidato natural dado o remoto já ser GitHub) quando o
harness de código for gerado.

## O que falta definir (bloqueado em decisão externa, não técnica)

- Provisão exata da `StorageClass` (qual cluster/cloud hospeda — impacta
  `provisioner` e parâmetros de zona).
- Provedor de e-mail transacional para `enviar_email_alerta`.
- Domínio: `insidelicitacoes.com.br` registrado; falta o DNS (registro.br)
  apontar para o EC2. Até lá, endereço provisório `16-59-20-70.sslip.io`.
- **Backup do Postgres fora da máquina:** todo deploy faz `pg_dump` antes
  de migrar (10 mais recentes, em `/opt/licita/backups/`), mas eles ficam
  no próprio EC2. Se a máquina for perdida, vão junto. Falta copiar para
  fora (S3, por exemplo).

## CI e imagens

Build manual, não em cada push — `.github/workflows/build-image.yml`
(dropdown `frontend`/`backend`/`both`). Builda a imagem
(`frontend/Dockerfile`, `backend/Dockerfile`) e publica em
`ghcr.io/vastimv/licita-ec2-frontend` / `licita-ec2-backend`, com a tag
`latest` (produção) ou `teste` (ambiente de teste). Normalmente ninguém roda
este workflow sozinho: **Deploy EC2** e **Teste: ligar** chamam ele antes de
atualizar o servidor.

O Dockerfile do frontend roda a suíte de testes como parte do build: a
imagem só existe se os testes passaram.

## Produção — EC2 com docker compose

Este repositório roda num **EC2 só** (AWS, us-east-2, IP fixo), sem
Kubernetes: `deploy/ec2/docker-compose.yml` sobe as mesmas imagens com
Postgres, RabbitMQ, worker, beat e **Caddy** (HTTPS automático via Let's
Encrypt; faz o papel do Ingress: `/api` → backend, o resto → frontend).

| Botão (GitHub Actions) | O que faz |
|---|---|
| **Deploy EC2** | gera as imagens `latest` (opcional) e roda `deploy/ec2/atualizar.sh` no servidor por SSH: baixa as imagens, roda `migrate`, sobe o que mudou e recarrega o Caddy |
| **Teste: ligar** | gera as imagens `teste` da branch escolhida e sobe `deploy/ec2/docker-compose.teste.yml` — outro banco, outras senhas, `teste.<domínio>` |
| **Teste: desligar** | para o teste (opção de apagar o banco do teste) |

Segredos do GitHub: `EC2_HOST` (o IP) e `EC2_SSH_KEY` (a chave `.pem`). As
senhas do sistema ficam só no servidor, em `/opt/licita/.env` (produção) e
`/opt/licita-teste/.env` (teste), geradas na instalação — **guarde uma
cópia fora do servidor**. Passo a passo completo, inclusive recriar a
máquina do zero: [`deploy/ec2/README.md`](../deploy/ec2/README.md).

## Kubernetes — o que já existe

Namespace `inside-solutions-licita` e o Deployment/Service do frontend, via
`kubectl apply -f k8s/` (sem GitOps ainda). Ver
[`k8s/README.md`](../k8s/README.md) para o passo a passo, inclusive como
criar o `Secret` de pull do GHCR — nunca commitado, sempre criado
imperativamente no cluster.

## Próximos passos possíveis

`integracoes`, `catalogo` e `licitacoes` já existem, com RabbitMQ,
`sincronizador-catalogo-pdm` e `celery-beat` no ar (ver
[`DOMINIO.md`](DOMINIO.md) para o estado detalhado e os achados contra a
API real). Falta:

1. **Torre de Controle:** Sentinela, Telegram, Radar, telas de lançamento
   manual — lista e ordem em [`TORRE.md`](TORRE.md), seção 11.
2. Fechar a causa raiz da desconexão do PNCP (mitigada com retry, não
   resolvida — ver `DOMINIO.md`) e a lentidão da busca textual por termo
   genérico (~2min observados).
3. Camada 3 da busca (embedding, pod separado) — desenho já fechado em
   `DOMINIO.md`, implementação pendente.
