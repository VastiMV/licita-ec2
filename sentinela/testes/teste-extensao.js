// Teste de ponta a ponta da extensão: Chromium de verdade, o Compras.gov
// simulado com as respostas reais de backend/apps/sentinela/exemplos, e o
// Licita rodando em http://127.0.0.1:8000 com SENTINELA_CHAVE=chave-local-de-teste.
// Uso: node sentinela/testes/teste-extensao.js [pasta-de-saida] [codigo-da-compra]
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const EXT = path.resolve(__dirname, "..");
const EX = path.resolve(__dirname, "../../backend/apps/sentinela/exemplos");
const OUT = process.argv[2] || require("os").tmpdir();
const ex = (n) => JSON.parse(fs.readFileSync(path.join(EX, n + ".json")));
const exemplos = ["participacoes", "meus_itens_56", "proposta_61_item_22"].map(
  ex,
);

(async () => {
  const ctx = await chromium.launchPersistentContext(
    OUT + "/perfil-" + Date.now(),
    {
      headless: false,
      args: [
        "--headless=new",
        `--disable-extensions-except=${EXT}`,
        `--load-extension=${EXT}`,
      ],
      viewport: { width: 1366, height: 800 },
    },
  );
  let [sw] = ctx.serviceWorkers();
  if (!sw) sw = await ctx.waitForEvent("serviceworker");
  const id = sw.url().split("/")[2];
  console.log("extensão carregada:", id);

  const opcoes = await ctx.newPage();
  await opcoes.goto(`chrome-extension://${id}/opcoes.html`);
  await opcoes.evaluate(() =>
    chrome.storage.local.set({
      licita: "http://127.0.0.1:8000",
      chave: "chave-local-de-teste",
    }),
  );

  // O "Compras.gov" de mentira: a página e as respostas reais gravadas.
  await ctx.route(
    "https://cnetmobile.estaleiro.serpro.gov.br/**",
    async (route) => {
      const u = new URL(route.request().url());
      const achado = exemplos.find(
        (e) => new URL(e.url).pathname === u.pathname,
      );
      if (achado)
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(achado.dados),
        });
      const urls = exemplos.map(
        (e) => e.url + (e.url.includes("?") ? "&" : "?") + "captcha=ABC123",
      );
      return route.fulfill({
        status: 200,
        contentType: "text/html",
        body: `<!doctype html><html><body><h1>Compras.gov (simulado)</h1><script>
        const urls = ${JSON.stringify(urls)};
        // um por XHR (como o Angular), os outros por fetch
        const x = new XMLHttpRequest(); x.open('GET', urls[0]); x.send();
        setTimeout(() => fetch(urls[1]), 800);
        setTimeout(() => fetch(urls[2]), 1600);
      </script></body></html>`,
      });
    },
  );

  const pagina = await ctx.newPage();
  const erros = [];
  pagina.on("pageerror", (e) => erros.push(String(e)));
  pagina.on("console", (m) =>
    erros.push("console " + m.type() + ": " + m.text()),
  );
  await pagina.goto(
    "https://cnetmobile.estaleiro.serpro.gov.br/comprasnet-web/seguro/fornecedor/participacoes",
  );
  await pagina.waitForTimeout(5000);
  const estado = await opcoes.evaluate(() =>
    chrome.storage.local.get(["ultimaCaptura", "ultimoErro"]),
  );
  console.log("estado da extensão:", JSON.stringify(estado));

  // A camada de disputa numa tela de compra
  await pagina.goto(
    "https://cnetmobile.estaleiro.serpro.gov.br/comprasnet-web/seguro/fornecedor/disputa?compra=" +
      (process.argv[3] || "15812705000612026"),
  );
  await pagina
    .waitForSelector(".sentinela-camada", { timeout: 10000 })
    .catch(() => {});
  await pagina.waitForTimeout(1500);
  console.log(
    "camada:",
    (
      await pagina
        .locator(".sentinela-camada")
        .innerText()
        .catch(() => "NÃO APARECEU")
    ).replace(/\n+/g, " | "),
  );
  await pagina.screenshot({ path: OUT + "/camada.png" });
  console.log("erros na página:", erros.length ? erros : "nenhum");
  await ctx.close();
})();
