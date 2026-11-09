// Teste de ponta a ponta da ronda: a Sentinela lê SOZINHA a lista de
// propostas de um item (sem captcha), com a sessão que a página usa.
//
// - Compras.gov simulado: a página faz uma consulta com `authorization:
//   Bearer …` (como a de verdade); a lista de propostas só responde com esse
//   cabeçalho (sem ele: 403, como o Compras.gov). Resposta = a real de
//   Cubatão 55/2026, item 2 (backend/apps/sentinela/exemplos).
// - Licita em http://127.0.0.1:8000 com SENTINELA_CHAVE=chave-local-de-teste
//   e o item 2 de Cubatão como item participado (classificação 23).
// Uso: node sentinela/testes/teste-ronda-propostas.js [pasta-de-saida]
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const EXT = path.resolve(__dirname, '..');
const EX = path.resolve(__dirname, '../../backend/apps/sentinela/exemplos');
const OUT = process.argv[2] || require('os').tmpdir();
const cubatao = JSON.parse(fs.readFileSync(path.join(EX, 'propostas_cubatao_item_2.json')));
const TOKEN = 'Bearer token-de-mentira-so-do-teste';

(async () => {
  const ctx = await chromium.launchPersistentContext(OUT + '/perfil-' + Date.now(), {
    headless: false,
    args: ['--headless=new', `--disable-extensions-except=${EXT}`, `--load-extension=${EXT}`],
  });
  let [sw] = ctx.serviceWorkers();
  if (!sw) sw = await ctx.waitForEvent('serviceworker');
  const id = sw.url().split('/')[2];
  const opcoes = await ctx.newPage();
  await opcoes.goto(`chrome-extension://${id}/opcoes.html`);
  await opcoes.evaluate(() => chrome.storage.local.set({ licita: 'http://127.0.0.1:8000', chave: 'chave-local-de-teste' }));

  const pedidos = [];
  await ctx.route('https://cnetmobile.estaleiro.serpro.gov.br/**', async (route) => {
    const req = route.request();
    const u = new URL(req.url());
    if (u.pathname.startsWith('/comprasnet-') && !u.pathname.startsWith('/comprasnet-web/')) {
      pedidos.push(`${req.method()} ${u.pathname}${u.search} auth=${req.headers()['authorization'] === TOKEN ? 'sim' : 'não'}`);
      if (req.headers()['authorization'] !== TOKEN) return route.fulfill({ status: 403, body: 'Forbidden' });
      if (u.pathname.endsWith('/favoritas/dentre-opcoes'))
        return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
      if (u.pathname === new URL(cubatao.url).pathname)
        return route.fulfill({ status: 206, contentType: 'application/json', body: JSON.stringify(cubatao.dados) });
      return route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
    }
    return route.fulfill({
      status: 200,
      contentType: 'text/html',
      body: `<!doctype html><html><body><h1>Compras.gov (simulado)</h1><script>
        fetch('/comprasnet-usuario/v1/usuario', { headers: { authorization: '${TOKEN}', 'x-version-number': '6.4.4' } });
      </script></body></html>`,
    });
  });

  const pagina = await ctx.newPage();
  await pagina.goto('https://cnetmobile.estaleiro.serpro.gov.br/comprasnet-web/seguro/fornecedor/compras');
  await pagina.waitForTimeout(1500);

  const estado = await opcoes.evaluate(() => chrome.runtime.sendMessage({ tipo: 'ronda_agora' }));
  console.log('pedidos ao Compras.gov:\n  ' + pedidos.join('\n  '));
  console.log('estado:', JSON.stringify(estado));
  await ctx.close();
})();
