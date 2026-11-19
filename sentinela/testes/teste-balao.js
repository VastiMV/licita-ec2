// Teste do balão (0.2.9, GEN-104): a Sentinela busca no Licita os avisos
// "Precisa de você" e mostra um balão do Windows para cada um novo.
//
// Chromium de verdade com a extensão; um Licita falso em 127.0.0.1 responde
// `GET /api/sentinela/avisos/`. Não precisa do Licita de verdade.
// Uso: node sentinela/testes/teste-balao.js
const { chromium } = require("playwright");
const http = require("http");
const os = require("os");
const path = require("path");

const EXT = path.resolve(__dirname, "..");
const CHAVE = "chave-local-de-teste";

let falhas = 0;
function confere(nome, ok, detalhe) {
  console.log(`${ok ? "ok  " : "FALHOU"}  ${nome}${ok ? "" : "  → " + detalhe}`);
  if (!ok) falhas += 1;
}

const pedidos = [];
let resposta = { ultimo: 5, avisos: [] };
const servidor = http.createServer((req, res) => {
  pedidos.push({ url: req.url, chave: req.headers["x-sentinela-chave"] });
  res.writeHead(200, { "Content-Type": "application/json" });
  res.end(JSON.stringify(resposta));
});

(async () => {
  await new Promise((pronto) => servidor.listen(0, "127.0.0.1", pronto));
  const licita = `http://127.0.0.1:${servidor.address().port}`;

  const ctx = await chromium.launchPersistentContext(path.join(os.tmpdir(), `perfil-balao-${Date.now()}`), {
    headless: false,
    args: ["--headless=new", `--disable-extensions-except=${EXT}`, `--load-extension=${EXT}`],
  });
  let [sw] = ctx.serviceWorkers();
  if (!sw) sw = await ctx.waitForEvent("serviceworker");
  await sw.evaluate((c) => chrome.storage.local.set(c), { licita, chave: CHAVE });

  // 1. Primeira vez: só anota o último id, sem balão (nada de balões antigos).
  await sw.evaluate(() => buscarAvisos());
  let baloes = await sw.evaluate(() => chrome.notifications.getAll());
  let guardado = await sw.evaluate(() => chrome.storage.local.get("avisoUltimo"));
  confere("1ª vez: pede sem 'depois' e com a chave", pedidos[0].url === "/api/sentinela/avisos/" && pedidos[0].chave === CHAVE, JSON.stringify(pedidos));
  confere("1ª vez: nenhum balão", Object.keys(baloes).length === 0, JSON.stringify(baloes));
  confere("1ª vez: guarda o último id", guardado.avisoUltimo === 5, JSON.stringify(guardado));

  // 2. Chegou a mensagem do pregoeiro: um balão, e pede só o que veio depois.
  resposta = {
    ultimo: 9,
    avisos: [{ id: 9, titulo: "Mensagem do pregoeiro · Pregão 61/2026", texto: "Envie o anexo em 2 horas." }],
  };
  await sw.evaluate(() => buscarAvisos());
  baloes = await sw.evaluate(() => chrome.notifications.getAll());
  guardado = await sw.evaluate(() => chrome.storage.local.get("avisoUltimo"));
  confere("depois: pede só os novos", pedidos[1].url === "/api/sentinela/avisos/?depois=5", JSON.stringify(pedidos));
  confere("aviso novo vira balão", Object.keys(baloes).includes("aviso-9"), JSON.stringify(baloes));
  confere("guarda o novo último id", guardado.avisoUltimo === 9, JSON.stringify(guardado));

  // 3. Licita fora do ar: não quebra, guarda o erro.
  servidor.close();
  await sw.evaluate(() => buscarAvisos());
  const erro = await sw.evaluate(() => chrome.storage.local.get("ultimoErro"));
  confere("Licita fora do ar: guarda o erro e não quebra", String(erro.ultimoErro && erro.ultimoErro.valor).startsWith("avisos:"), JSON.stringify(erro));

  const versao = await sw.evaluate(() => chrome.runtime.getManifest().version);
  confere("versão 0.2.9", versao === "0.2.9", versao);

  await ctx.close();
  console.log(falhas ? `\n${falhas} falha(s)` : "\ntudo certo");
  process.exit(falhas ? 1 : 0);
})();
