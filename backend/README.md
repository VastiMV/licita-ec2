# Backend

Django 6 + Django REST Framework, servido via Daphne (ASGI) — pronto para
`async def` e para o Channels quando o primeiro consumer de websocket
existir. Ver [`docs/ARQUITETURA.md`](../docs/ARQUITETURA.md) (raiz do
repositório) para o desenho geral e [`docs/DOMINIO.md`](../docs/DOMINIO.md)
para o domínio de negócio.

## Rodando localmente

Sempre dentro do venv — nunca instale dependência no Python do sistema.

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

cp .env.example .env    # ajuste se necessário
export $(cat .env | xargs)   # ou exporte as variáveis do jeito que preferir

.venv/bin/python manage.py migrate
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py runserver     # via Daphne — ver INSTALLED_APPS em config/settings/base.py
```

Precisa de um Postgres rodando e acessível com as credenciais de `.env`
(`POSTGRES_*`) — não há fallback para SQLite: o resto do projeto já assume
Postgres (ver docs/ARQUITETURA.md), e testar contra outro banco esconderia
diferença de comportamento real.

## Testes

```bash
.venv/bin/python manage.py test apps.accounts
```

Test runner nativo do Django (`django.test.TestCase`) — ver "Estratégia de
testes" em `docs/ARQUITETURA.md`: teste vem antes do código, não depois.

## Estrutura

```
config/
  settings/
    environment.py   Environment — única porta de entrada para variável de ambiente
                      (ConfigMap/Secret no Kubernetes). Nenhum outro módulo lê os.environ.
    base.py           settings do Django, montado em cima de Environment
  asgi.py             Daphne + Channels (roteador de websocket vazio por enquanto)
  celery.py           app Celery (tasks em catalogo e capag; agenda no banco, django-celery-beat)
  urls.py
apps/
  accounts/           User (login por e-mail) — primeiro model, AUTH_USER_MODEL
  integracoes/        Clients HTTP (compras.gov.br, PNCP) — isolados, mockáveis nos testes
  catalogo/           Model Pdm, sync assíncrono (Celery) e busca por similaridade
  capag/              Nota CAPAG (Tesouro) de municípios/estados — selo do card
  licitacoes/         Busca de oportunidades (ao vivo, sem persistir), oportunidades
                      salvas e o histórico de cada uma (models.py), o Ciclo de
                      Licitação (ciclo.py) e a saída do ciclo — Encerradas ×
                      Descartadas (encerradas.py)
  tenants/            Tenant — de quem são os registros (uma linha só hoje)
  empresas/           Os CNPJs com que a equipe disputa
  documentos/         Dossiê de habilitação da empresa (certidões, validade, versões)
  fornecedores/       De quem a equipe compra para revender
  produtos/           Fabricante › Marca › Modelo, afinidade e tabela de preços
  cotador/            Formação de preço (formulas.py) e a planilha .xlsx (planilha.py)
  propostas/          A proposta em Word e os arquivos da licitação
  armazenamento/      Onde os arquivos ficam (R2, S3, disco) — configurado na tela
```

Cada `models.py` começa com uma docstring explicando as decisões daquele
domínio — é o primeiro lugar a ler antes de mexer num app.

Ainda não existem: `filtros` e `alertas` (ver `docs/ARQUITETURA.md`).

## Variáveis de ambiente

Ver [`.env.example`](.env.example) para a lista completa e o que cada uma
faz. Todas são lidas por `Environment` (`config/settings/environment.py`),
nunca direto por `os.environ` em outro lugar do código.
