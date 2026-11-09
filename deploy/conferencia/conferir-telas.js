// Conferência das telas do Licita SÓ COM LEITURA (pedido de 09/11/2026).
//
// Não faz login: a LEITURA_CHAVE do servidor chega pelo proxy do ambiente
// do assistente (`Authorization: Bearer <chave>`, injetado no lugar do token
// da tela) — este script nunca vê a chave. A "renovação de sessão" do Licita é respondida aqui com um
// token de mentira só para a tela abrir; o backend autentica pela chave e
// só aceita leitura (apps/accounts/leitura.py). Qualquer gravação → 401.
//
// Uso: node deploy/conferencia/conferir-telas.js <pasta-de-saida> [endereço]
//      (endereço padrão: https://insidelicitacoes.com.br)
// Local: LEITURA_LOCAL=<chave> para mandar o cabeçalho sem proxy.
const { chromium } = require('playwright');
const fs = require('fs');

const OUT = process.argv[2] || '.';
const BASE = (process.argv[3] || 'https://insidelicitacoes.com.br').replace(/\/+$/, '');
const TELAS = [
  '/torre',
  '/torre/estagio/preparar',
  '/torre/estagio/disputar',
  '/torre/estagio/contratar',
  '/torre/estagio/receber',
  '/torre/etapa/disputa',
  '/torre/etapa/aguardando_julgamento',
  '/torre/etapa/julgado_habilitado',
  '/torre/etapa/aguardando_adjudicacao',
  '/torre/etapa/homologado',
  '/torre/etapa/contrato',
  '/torre/etapa/empenho',
  '/oportunidades/salvas',
  '/ciclo/cotador',
  '/ciclo/encerradas',
  '/ciclo/descartadas',
];

function tokenDeMentira() {
  const b64 = (o) => Buffer.from(JSON.stringify(o)).toString('base64url');
  const agora = Math.floor(Date.now() / 1000);
  return `${b64({ alg: 'none' })}.${b64({ user_id: 0, email: 'leitura@licita.interno', nome: 'Leitura', exp: agora + 3600, login_em: agora })}.x`;
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const navegador = await chromium.launch(
    process.env.HTTPS_PROXY && !process.env.LEITURA_LOCAL ? { proxy: { server: process.env.HTTPS_PROXY } } : {},
  );
  const ctx = await navegador.newContext({
    viewport: { width: 1440, height: 900 },
    ignoreHTTPSErrors: false,
    extraHTTPHeaders: process.env.LEITURA_LOCAL ? { 'X-Licita-Leitura-Token': process.env.LEITURA_LOCAL } : {},
  });
  const api = {};
  await ctx.route('**/api/auth/refresh/', (r) =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ access: tokenDeMentira() }) }),
  );
  const problemas = [];
  ctx.on('response', async (resp) => {
    const u = new URL(resp.url());
    if (!u.pathname.startsWith('/api/')) return;
    if (resp.status() >= 400) problemas.push(`${resp.status()} ${resp.request().method()} ${u.pathname}${u.search}`);
    if (resp.request().method() === 'GET' && resp.ok()) {
      try {
        api[u.pathname + u.search] = await resp.json();
      } catch {}
    }
  });
  const p = await ctx.newPage();
  p.on('pageerror', (e) => problemas.push('erro na página: ' + e));
  for (const tela of TELAS) {
    await p.goto(BASE + tela, { waitUntil: 'networkidle' }).catch((e) => problemas.push(`${tela}: ${e}`));
    await p.waitForTimeout(600);
    const nome = tela.replace(/\//g, '_').replace(/^_/, '') || 'inicio';
    await p.screenshot({ path: `${OUT}/${nome}.png`, fullPage: true });
    fs.writeFileSync(`${OUT}/${nome}.txt`, await p.locator('main, body').first().innerText());
  }
  fs.writeFileSync(`${OUT}/api.json`, JSON.stringify(api, null, 1));
  fs.writeFileSync(`${OUT}/problemas.txt`, problemas.join('\n'));
  console.log(`telas: ${TELAS.length} · respostas da API: ${Object.keys(api).length} · problemas: ${problemas.length}`);
  if (problemas.length) console.log(problemas.slice(0, 15).join('\n'));
  await navegador.close();
})();
