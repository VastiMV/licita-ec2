// Teste da sessão da ronda (0.2.8, GEN-45): a Sentinela usa o token ATUAL
// que o site guarda no sessionStorage (`accessToken`) e, se levar 401, espera
// o site renovar e tenta 1 vez antes de desistir. Ela nunca chama o retoken.
//
// Sem extensão e sem Licita: carrega só o pagina.js numa página do
// Compras.gov simulado e conversa com ele como a ponte conversa.
// Uso: node sentinela/testes/teste-retoken.js
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const PAGINA = fs.readFileSync(path.resolve(__dirname, "../pagina.js"), "utf8");
const ORIGEM = "https://cnetmobile.estaleiro.serpro.gov.br";
const CAMINHO = "/comprasnet-mensagem/v1/mensagens?size=10&page=0";

let falhas = 0;
function confere(nome, ok, detalhe) {
  console.log(`${ok ? "ok  " : "FALHOU"}  ${nome}${ok ? "" : "  → " + detalhe}`);
  if (!ok) falhas += 1;
}

async function novaPagina(navegador, validos) {
  const pagina = await navegador.newPage();
  const pedidos = [];
  await pagina.route(`${ORIGEM}/**`, (route) => {
    const req = route.request();
    const u = new URL(req.url());
    if (u.pathname.startsWith("/comprasnet-mensagem/")) {
      const auth = req.headers()["authorization"] || "";
      pedidos.push(auth);
      if (u.pathname.endsWith("/retoken")) pedidos.push("RETOKEN!");
      return validos.has(auth)
        ? route.fulfill({ status: 200, contentType: "application/json", body: "[]" })
        : route.fulfill({ status: 401, body: "" });
    }
    return route.fulfill({ status: 200, contentType: "text/html", body: "<!doctype html><h1>Compras.gov (simulado)</h1>" });
  });
  await pagina.addInitScript(PAGINA);
  await pagina.goto(`${ORIGEM}/comprasnet-web/seguro/fornecedor/compras`);
  return { pagina, pedidos };
}

// Pede uma consulta como a ponte pede e devolve a resposta da página.
function consultar(pagina, aoEsperar) {
  return pagina.evaluate(
    ({ caminho, aoEsperar }) =>
      new Promise((resolver) => {
        const id = Math.random().toString(36).slice(2);
        window.addEventListener("message", (e) => {
          if (e.data && e.data.tipo === "resposta" && e.data.id === id) resolver(e.data);
        });
        window.postMessage({ sentinela: true, tipo: "pedido", id, metodo: "GET", caminho }, location.origin);
        // O site renova a sessão enquanto a Sentinela espera.
        if (aoEsperar) setTimeout(() => sessionStorage.setItem("accessToken", aoEsperar), 1000);
      }),
    { caminho: CAMINHO, aoEsperar },
  );
}

(async () => {
  const navegador = await chromium.launch();

  // 1. Cópia velha na memória, token novo no sessionStorage: usa o novo.
  {
    const { pagina, pedidos } = await novaPagina(navegador, new Set(["Bearer novo"]));
    await pagina.evaluate(() => {
      sessionStorage.setItem("accessToken", "novo");
      fetch("/comprasnet-usuario/v1/usuario", { headers: { authorization: "Bearer velho" } });
    });
    const r = await consultar(pagina);
    confere("usa o token atual do sessionStorage (sem 'Bearer')", r.status === 200 && pedidos[0] === "Bearer novo", JSON.stringify({ r, pedidos }));
    await pagina.close();
  }

  // 2. Valor guardado como texto JSON (com aspas) e já com "Bearer".
  {
    const { pagina, pedidos } = await novaPagina(navegador, new Set(["Bearer abc"]));
    await pagina.evaluate(() => sessionStorage.setItem("accessToken", JSON.stringify("Bearer abc")));
    const r = await consultar(pagina);
    confere("aceita o valor com aspas e com 'Bearer'", r.status === 200 && pedidos[0] === "Bearer abc", JSON.stringify({ r, pedidos }));
    await pagina.close();
  }

  // 3. Sem sessionStorage: continua usando o que copiou da página (como antes).
  {
    const { pagina, pedidos } = await novaPagina(navegador, new Set(["Bearer copiado"]));
    await pagina.evaluate(() => fetch("/comprasnet-usuario/v1/usuario", { headers: { authorization: "Bearer copiado" } }));
    const r = await consultar(pagina);
    confere("sem sessionStorage, usa a cópia da página", r.status === 200 && pedidos[0] === "Bearer copiado", JSON.stringify({ r, pedidos }));
    await pagina.close();
  }

  // 4. 401, o site renova durante a espera: tenta 1 vez e dá certo.
  {
    const { pagina, pedidos } = await novaPagina(navegador, new Set(["Bearer renovado"]));
    await pagina.evaluate(() => sessionStorage.setItem("accessToken", "vencido"));
    const inicio = Date.now();
    const r = await consultar(pagina, "renovado");
    const ok = r.status === 200 && pedidos.join(",") === "Bearer vencido,Bearer renovado";
    confere("401 + site renovou: tenta de novo 1 vez e lê", ok, JSON.stringify({ r, pedidos }));
    confere("esperou o site (alguns segundos)", Date.now() - inicio >= 3000, `${Date.now() - inicio} ms`);
    await pagina.close();
  }

  // 5. 401 e o site não renova: 401 uma vez só; a próxima é "sem_sessao".
  {
    const { pagina, pedidos } = await novaPagina(navegador, new Set());
    await pagina.evaluate(() => sessionStorage.setItem("accessToken", "vencido"));
    const r1 = await consultar(pagina);
    const r2 = await consultar(pagina);
    confere("site não renovou: devolve 401 sem repetir", r1.status === 401 && pedidos.length === 1, JSON.stringify({ r1, pedidos }));
    confere("depois do 401, mesmo token = sem_sessao (não insiste)", r2.erro === "sem_sessao" && pedidos.length === 1, JSON.stringify({ r2, pedidos }));
    confere("nunca chama o retoken", !pedidos.includes("RETOKEN!"), JSON.stringify(pedidos));
    await pagina.close();
  }

  // 6. Depois de cair, o Carlinhos entra de novo: volta a ler sozinha.
  {
    const { pagina } = await novaPagina(navegador, new Set(["Bearer login-novo"]));
    await pagina.evaluate(() => sessionStorage.setItem("accessToken", "vencido"));
    await consultar(pagina);
    await pagina.evaluate(() => sessionStorage.setItem("accessToken", "login-novo"));
    const r = await consultar(pagina);
    confere("login novo depois da queda: volta a ler", r.status === 200, JSON.stringify(r));
    await pagina.close();
  }

  await navegador.close();
  console.log(falhas ? `\n${falhas} falha(s)` : "\ntudo certo");
  process.exit(falhas ? 1 : 0);
})();
