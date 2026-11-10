# AGENTS.md — regras para agentes de IA neste repositório

Vale para qualquer agente (Claude Code, Codex e outros). Regras
**obrigatórias**, combinadas com a operação em 10/11/2026.

O que é o projeto: [`README.md`](README.md). Regras de negócio e decisões:
pasta [`docs/`](docs/).

## 1. Decisões são da operação, não do agente

- Antes de qualquer **decisão de produto**, **regra de negócio**, **mudança
  de comportamento**, **escolha entre opções** ou **ação fora do repositório**
  (merge, deploy, Jira, GitHub, banco): **pare, mostre as opções com uma
  recomendação e espere a confirmação**.
- Pode fazer **sem perguntar**: ler código e documentos, consultar dados só
  para leitura, rodar testes, montar análises.
- Uma aprovação vale **só para aquilo** que foi aprovado. Não vale para o
  próximo passo.
- Quando a documentação e o código **discordam**, não escolha sozinho qual
  está certo: **pergunte**. Pode ser a documentação desatualizada ou um bug
  no código.
- O que não estiver no código nem nos documentos fica marcado como
  **"a confirmar"**. Nunca preencher no chute.

## 2. Documentação junto com o código

- **Toda mudança conta**: regra de negócio, tela, estilo, refatoração,
  endpoint, banco, integração, variável de ambiente, Sentinela, deploy.
- A documentação é atualizada **no mesmo PR** da mudança.
- Se um PR realmente não precisa mudar a documentação, o texto do PR traz a
  linha: `Sem mudança de documentação: <motivo>`.
- Onde escrever:

  | Assunto | Documento |
  |---|---|
  | Regras de negócio, entidades, decisões | `docs/DOMINIO.md` |
  | Torre de Controle (etapas, saídas, regras) | `docs/TORRE.md` |
  | Sentinela (extensão, ronda, captura) | `docs/SENTINELA.md` |
  | Endereços do Compras.gov | `docs/COMPRAS_GOV.md` |
  | Arquitetura, stack, deploy | `docs/ARQUITETURA.md` |
  | Plano e andamento | `docs/Tarefas/` |
  | Visão geral e como rodar | `README.md` |

- Cada mudança de regra ganha a **data** e o **porquê** (o caso real que
  motivou, ex.: "Guarulhos 461/2026").

## 3. Jira

- Projeto **GEN** ("Time dos Gênios Burros"), site
  `insidesolutions-brasil.atlassian.net`.
- Todo trabalho tem um cartão. O **código do cartão** vai no nome do ramo
  (`GEN-48-descricao`) e no **título do PR** (`GEN-48: …`).
- Status: To Do → In Progress (ao começar) → Done (publicado).

## 4. Segredos e dados sensíveis

Nunca em código, documento, commit, PR, cartão ou comentário:

- chaves, tokens, senhas, valores do `.env`;
- IP e endereço interno do servidor (EC2);
- e-mails pessoais e dados de terceiros (CNPJ/CPF de fornecedores e de
  pessoas).

## 5. Testes antes do PR

Rodar os testes do que foi mexido e informar o resultado no PR.

- Backend (precisa de Postgres; ver `backend/README.md`):
  `cd backend && .venv/bin/python manage.py test apps.<app>`
- Frontend: `cd frontend && npx ng test --watch=false`

Teste que falha **não** é desligado nem pulado para passar.

## 6. Produção

- **Nada de merge, deploy ou escrita no banco de produção sem aprovação**
  explícita, uma por vez.
- Os workflows de deploy (`.github/workflows/deploy-ec2.yml`,
  `build-image.yml`, `teste-*.yml`) só mudam com aprovação.
- Conferência de produção é só leitura (`Consultar EC2`, chave de leitura).

## 7. Jeito de escrever

Para quem lê (operação com TEA, TDAH e dislexia), em respostas **e** na
documentação:

- português, direto ao ponto, sem rodeio;
- frases curtas, passos numerados, tabelas quando ajudam;
- dizer o que é fato e o que é suposição.
