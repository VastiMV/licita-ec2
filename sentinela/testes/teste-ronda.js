// Teste de ponta a ponta da ronda e das tarefas (Sentinela 0.2): Chromium de
// verdade, Compras.gov simulado com as respostas reais de
// backend/apps/sentinela/exemplos, Licita em http://127.0.0.1:8000 com
// SENTINELA_CHAVE=chave-local-de-teste e uma tarefa "desfavoritar" pendente.
// Uso: node sentinela/testes/teste-ronda.js [pasta-de-saida]
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const EXT = path.resolve(__dirname, "..");
const EX = path.resolve(__dirname, "../../backend/apps/sentinela/exemplos");
const OUT = process.argv[2] || require("os").tmpdir();
const ex = (n) => JSON.parse(fs.readFileSync(path.join(EX, n + ".json")));
const SESSAO = "Bearer TOKEN-DE-TESTE";

(async () => {
  const ctx = await chromium.launchPersistentContext(
    OUT + "/perfil-ronda-" + Date.now(),
    {
      headless: false,
      args: [
        "--headless=new",
        `--disable-extensions-except=${EXT}`,
        `--load-extension=${EXT}`,
      ],
    },
  );
  let [sw] = ctx.serviceWorkers();
  if (!sw) sw = await ctx.waitForEvent("serviceworker");
  const id = sw.url().split("/")[2];
  const opcoes = await ctx.newPage();
  await opcoes.goto(`chrome-extension://${id}/opcoes.html`);
  await opcoes.evaluate(() =>
    chrome.storage.local.set({
      licita: "http://127.0.0.1:8000",
      chave: "chave-local-de-teste",
    }),
  );

  const chamadas = [];
  const recursal = ex("fase_recursal_56_item_22").dados;
  await ctx.route(
    "https://cnetmobile.estaleiro.serpro.gov.br/**",
    async (route) => {
      const req = route.request();
      const u = new URL(req.url());
      if (u.pathname.startsWith("/comprasnet-web/")) {
        // A página: faz uma consulta qualquer mandando a sessão (como o Angular).
        return route.fulfill({
          status: 200,
          contentType: "text/html",
          body: `<!doctype html><html><body><h1>Compras.gov (simulado)</h1><script>
          const x = new XMLHttpRequest();
          x.open('GET', '/comprasnet-mensagem/v1/mensagens/quantidade-nao-lidas');
          x.setRequestHeader('authorization', '${SESSAO}');
          x.setRequestHeader('x-version-number', '6.4.4');
          x.send();
        </script></body></html>`,
        });
      }
      chamadas.push({
        metodo: req.method(),
        caminho: u.pathname + u.search,
        sessao: req.headers()["authorization"] || "",
      });
      if (u.pathname.endsWith("/fase-recursal-fornecedor/1")) {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(recursal),
        });
      }
      if (u.pathname.endsWith("/favorita") && req.method() === "DELETE")
        return route.fulfill({ status: 200, body: "" });
      if (u.pathname.endsWith("/favoritas/dentre-opcoes"))
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: "[]",
        });
      if (u.pathname.endsWith("/diligencias"))
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: "[]",
        });
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: "0",
      });
    },
  );

  const pagina = await ctx.newPage();
  await pagina.goto(
    "https://cnetmobile.estaleiro.serpro.gov.br/comprasnet-web/seguro/fornecedor/compras",
  );
  await pagina.waitForTimeout(1500);

  const estado = await opcoes.evaluate(() =>
    chrome.runtime.sendMessage({ tipo: "ronda_agora" }),
  );
  console.log("resultado da ronda:", JSON.stringify(estado));
  const daSentinela = chamadas.filter(
    (c) => !c.caminho.includes("quantidade-nao-lidas"),
  );
  console.log("consultas feitas pela Sentinela:", daSentinela.length);
  console.log(
    "todas com a sessão da página:",
    daSentinela.every((c) => c.sessao === SESSAO),
  );
  console.log(
    "alguma com captcha:",
    daSentinela.some((c) => c.caminho.includes("captcha")),
  );
  console.log(
    "tirou favorito:",
    daSentinela.filter((c) => c.metodo === "DELETE").map((c) => c.caminho),
  );
  await ctx.close();
})();
