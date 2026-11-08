# Sentinela — a extensão do Chrome (beta 0.1)

Lê o Compras.gov.br **na sessão do próprio Carlinhos** e manda para o Licita.
Plano, limites e o que cada endereço do Compras.gov traz:
[`docs/SENTINELA.md`](../docs/SENTINELA.md). Mapa de todos os endereços
(login, captcha, abre direto): [`docs/COMPRAS_GOV.md`](../docs/COMPRAS_GOV.md).

## O que esta versão faz

1. **Participações e itens.** Quando o Carlinhos abre, no Compras.gov, a
   tela de participações, uma compra ou a lista "meus itens", a Sentinela
   copia o que **a própria página recebeu** e manda para o Licita. A Torre
   se atualiza sozinha: compra nova aparece, cada item vai para a sua etapa,
   pedido de desconto e convocação de anexo viram alerta no cartão.
2. **Camada de disputa.** Em qualquer tela de uma compra, um painel no canto
   mostra, item a item, os números da cotação do Licita: **teto, ideal, piso,
   custo e lucro**. Amarelo: o ideal passa do teto. Vermelho: nem o piso cabe.
3. **Vigia.** A cada 3 minutos ela avisa o Licita que está viva (e se há uma
   aba do Compras.gov aberta). O botão "Sentinela" do topo do Licita fica
   verde, âmbar ou vermelho.

**0.1.2 (08/11/2026):** o painel da camada confere a cotação do Licita sozinho
a cada minuto, tem o botão ↻ (atualizar agora) e mostra a hora da última
atualização — antes ele lia uma vez só, ao abrir a compra.

**0.1.3 (08/11/2026):** o "Abrir" da Torre abre a compra numa **cópia da aba
do Compras.gov que já está logada** — a sessão do Compras.gov vale por aba,
e uma aba nova cairia no login. A aba original não é tocada. Sem Sentinela,
o Licita abre aba nova como antes (`licita.js` marca a página do Licita com
`data-sentinela`; `abrirNoCompras` em `torre-acoes.service.ts`).

## O que ela nunca faz

- Resolver, gerar ou burlar captcha.
- Guardar senha (gov.br ou Compras.gov).
- Enviar qualquer coisa ao Compras.gov (lance, proposta, anexo).
- Ler token de login: ela só copia respostas que a página já recebeu.

## Instalar (no computador do Carlinhos)

1. Baixe a pasta `sentinela` (o arquivo `sentinela.zip`) e descompacte num
   lugar **fixo** (ex.: `Documentos\Sentinela`). Se a pasta for apagada, a
   extensão para.
2. No Chrome, abra `chrome://extensions`.
3. Ligue **Modo do desenvolvedor** (canto de cima, à direita).
4. **Carregar sem compactação** → escolha a pasta `sentinela`.
5. Clique no ícone de quebra-cabeça → fixe a **Sentinela · Licita**. Clique
   nela:
   - **Endereço do Licita:** `https://insidelicitacoes.com.br` — **sem
     `www`**: o `www.` redireciona, e no redirecionamento o Chrome troca o
     envio por uma consulta (o Licita responde 405);
   - **Chave da Sentinela:** a `SENTINELA_CHAVE` do servidor (ver
     `deploy/ec2/README.md`, "Sentinela");
   - **Salvar** → **Testar conexão**. Deve aparecer "Último sinal de vida:
     agora (ok)".

## Usar

- Deixe **uma aba do Compras.gov aberta e logada** (a que ele já usa).
- Para trazer tudo de uma vez: abra **Minhas participações**, depois, em
  cada compra, a lista de itens com o filtro **"Meus itens"**.
- Durante a disputa, o painel aparece sozinho no canto (o botão "–" recolhe).

## Atualizar

Troque os arquivos da pasta pelos novos e, em `chrome://extensions`, clique
no ícone de recarregar da Sentinela.

## Para quem mexe no código

| Arquivo | O que faz |
|---|---|
| `pagina.js` | roda dentro da página do Compras.gov; copia as respostas que interessam (e avisa se a renovação da sessão falhar) |
| `ponte.js` | leva o que a página copiou até o fundo da extensão |
| `fundo.js` | manda ao Licita (`/api/sentinela/captura/`, `pulso/`, `camada/<código>/`) com a chave |
| `camada.js`, `camada.css` | o painel da camada de disputa |
| `opcoes.html`, `opcoes.js` | endereço do Licita, chave, teste de conexão |

**Toda a interpretação mora no backend** (`backend/apps/sentinela/ingestao.py`),
testada com respostas reais (`backend/apps/sentinela/exemplos/`). Se o
Compras.gov mudar o formato, é lá que se corrige — a extensão não precisa
mudar.

Testar a extensão de verdade (Chromium + Playwright, com o Compras.gov
simulado pelas respostas de `backend/apps/sentinela/exemplos/`):
`sentinela/testes/teste-extensao.js` (instruções no topo do arquivo).
