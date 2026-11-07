# Licita

Plataforma da **Inside Solutions** para encontrar, cotar e acompanhar
licitações públicas (Lei 14.133), integrando com o PNCP e o compras.gov.br.
A equipe busca oportunidades, salva as que interessam, monta a cotação
(Cotador), gera a proposta e acompanha cada uma pelo **Ciclo de Licitação**.

> **Chegou agora para mexer no sistema?** Leia nesta ordem:
> 1. este README (o que é, onde roda, como trabalhar);
> 2. [`docs/DOMINIO.md`](docs/DOMINIO.md) — as regras de negócio (o "porquê");
> 3. [`docs/ARQUITETURA.md`](docs/ARQUITETURA.md) — como o código se organiza;
> 4. [`deploy/ec2/README.md`](deploy/ec2/README.md) — o servidor e os botões
>    de deploy e de teste.

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
| **Produção** | `https://16-59-20-70.sslip.io` (provisório) → `https://insidelicitacoes.com.br` quando o DNS do registro.br for configurado | a branch `main` |
| **Teste** | `https://teste.16-59-20-70.sslip.io` | a branch que estiver em teste (liga e desliga sob demanda) |

Os dois rodam na mesma máquina (EC2 `licita`, região us-east-2, IP fixo
`16.59.20.70`), com bancos **separados**. Detalhes, senhas (onde ficam) e
como recriar a máquina: [`deploy/ec2/README.md`](deploy/ec2/README.md).

## Como trabalhar (o fluxo de toda mudança)

**A `main` é o que está no ar. Ninguém mexe direto nela.** Toda mudança:

1. **Branch nova** a partir da `main` — **um assunto por branch** (ex.: o
   logo e a regra de Descartadas foram branches separadas). Nome:
   `claude/<assunto>` ou `<seu-nome>/<assunto>`.
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

**Telas (menu):**

| Menu | Tela | O que faz |
|---|---|---|
| Ciclo de Licitação | Visão Geral | quadro com uma coluna por etapa (Oportunidade, Cotação, Proposta, Disputa, Empenho) |
| | Oportunidades › Buscar | busca ao vivo no PNCP/compras.gov.br, por palavra-chave ou UASG |
| | Oportunidades › Salvas | a lista da equipe — só o que ainda está no prazo |
| | Cotador | formação de preço por item, com comparação de fornecedores; exporta .xlsx |
| | Propostas | a proposta gerada a partir da cotação (Word + arquivos) |
| | Disputas, Empenhos | **ainda não existem** (a coluna aparece vazia) |
| | Encerradas | só o que **participou** do certame — vazia até Disputa/Empenho existirem |
| | Descartadas | tudo que saiu do ciclo antes de participar (tirada da lista ou prazo vencido, com ou sem cotação) |
| Cadastros | Empresas | os CNPJs com que a equipe disputa, e o dossiê de documentos de habilitação |
| | Fornecedores | de quem a equipe compra para revender |
| | Produtos | Fabricante › Marca › Modelo e quem vende cada fabricante |
| Configurações | Armazenamento | onde os arquivos ficam (R2, S3 ou disco) — só administrador |
| | Usuários | quem acessa o sistema — só administrador |

As regras de cada uma estão em [`docs/DOMINIO.md`](docs/DOMINIO.md).

**Ainda não existe:** filtros salvos e alertas por e-mail (o objetivo
original do produto), as etapas Disputa e Empenho, backup automático do
banco de produção.

## Estrutura do repositório

```
backend/         Django/DRF — ver backend/README.md
frontend/        Angular — ver frontend/README.md
deploy/ec2/      produção no EC2: docker compose, Caddy, scripts e o guia
k8s/             manifests Kubernetes (alternativa; usados no repositório original)
docs/            DOMINIO.md, ARQUITETURA.md, mockups e atas
.github/workflows/
  build-image.yml      gera as imagens (chamado pelos outros dois)
  deploy-ec2.yml       botão "Deploy EC2" — produção
  teste-ligar.yml      botão "Teste: ligar" — ambiente de teste
  teste-desligar.yml   botão "Teste: desligar"
```
