// O fundo da Sentinela: manda ao Licita o que a página capturou; a cada
// 3 minutos, o sinal de vida (o "vigia" do topo do Licita); a cada 10
// minutos, em horário de trabalho, a ronda (propostas dos itens da empresa,
// lidas na aba do Compras.gov — só endereços sem captcha).
//
// Configuração (opcoes.html): o endereço do Licita e a chave da Sentinela.
// A chave é a SENTINELA_CHAVE do servidor — não é senha de ninguém.

const VERSAO = chrome.runtime.getManifest().version;
const COMPRAS = "https://cnetmobile.estaleiro.serpro.gov.br/*";
const PADRAO = { licita: "https://insidelicitacoes.com.br", chave: "" };

async function configuracao() {
  const salvo = await chrome.storage.local.get(PADRAO);
  return {
    licita: (salvo.licita || "").replace(/\/+$/, ""),
    chave: salvo.chave || "",
  };
}

async function guardarUltimo(campo, valor) {
  await chrome.storage.local.set({
    [campo]: { valor, em: new Date().toISOString() },
  });
}

async function licita(caminho, opcoes = {}) {
  const { licita, chave } = await configuracao();
  if (!licita || !chave)
    throw new Error("Sentinela sem configuração: abra as opções.");
  const resposta = await fetch(`${licita}/api/sentinela/${caminho}`, {
    ...opcoes,
    headers: {
      "Content-Type": "application/json",
      "X-Sentinela-Chave": chave,
      ...(opcoes.headers || {}),
    },
  });
  if (resposta.redirected) {
    throw new Error(
      `O endereço ${licita} redireciona para ${new URL(resposta.url).origin}. ` +
        'Use esse endereço nas opções (sem "www").',
    );
  }
  const corpo = await resposta.json().catch(() => ({}));
  if (!resposta.ok)
    throw new Error(
      `Licita respondeu ${resposta.status}: ${JSON.stringify(corpo).slice(0, 200)}`,
    );
  return corpo;
}

async function pulso(estado, detalhe = "") {
  try {
    await licita("pulso/", {
      method: "POST",
      body: JSON.stringify({ estado, detalhe, versao: VERSAO }),
    });
    await guardarUltimo("ultimoPulso", estado);
    await chrome.action.setBadgeText({ text: estado === "ok" ? "" : "!" });
    await chrome.action.setBadgeBackgroundColor({ color: "#e0a12a" });
  } catch (erro) {
    await guardarUltimo("ultimoErro", String(erro.message || erro));
    await chrome.action.setBadgeText({ text: "×" });
    await chrome.action.setBadgeBackgroundColor({ color: "#c2381f" });
  }
}

// O vigia: há uma aba do Compras.gov aberta? (é nela que a sessão vive)
// 0.2.6 (GEN-45, 12/11/2026):
// - sem aba fora do horário de trabalho é normal: não avisa (eram ~200
//   avisos por semana, quase todos à noite e no domingo);
// - com a sessão fora, fica quieto: o topo do Licita continua no aviso da
//   queda (a última notícia) em vez de voltar ao verde a cada 3 minutos.
async function vigiar() {
  const abas = await chrome.tabs.query({ url: COMPRAS });
  if (!abas.length) {
    if (emHorarioDeTrabalho())
      await pulso("sem_aba", "Nenhuma aba do Compras.gov aberta");
    return;
  }
  if ((await sessaoAtual()) !== "ok") return;
  await pulso("ok");
}

// ---- a sessão do Compras.gov: uma queda, um aviso (GEN-45) -----------------
//
// Antes, cada ronda (10 em 10 min) avisava "sessão caiu" de novo enquanto
// ninguém fizesse login: 1 queda virava até 35 avisos. E o mesmo 401 era
// avisado duas vezes (pela página e pelo fundo). Agora o fundo guarda o
// estado e só avisa quando ele **muda**: caiu, sem sessão na aba, voltou.

async function sessaoAtual() {
  const { sessao } = await chrome.storage.local.get({ sessao: "ok" });
  return sessao;
}

async function marcarSessao(estado, detalhe = "") {
  const atual = await sessaoAtual();
  if (atual === estado) return;
  // Depois de um 401 a página apaga o token, e a ronda seguinte vê "sem
  // sessão": é a mesma queda, não um aviso novo.
  if (atual === "sessao_caiu" && estado === "sem_sessao") return;
  await chrome.storage.local.set({ sessao: estado });
  await pulso(
    estado,
    estado === "ok" ? "A sessão do Compras.gov voltou" : detalhe,
  );
}

// Manda à aba uma lista de consultas; ela faz uma de cada vez, com pausa.
async function executarNaAba(pedidos) {
  // Só a aba da área do fornecedor tem a sessão (0.2.6): a pública dava
  // "sem sessão" e virava aviso de queda.
  const aba = await abaDoCompras({ soLogada: true });
  if (!aba) {
    const abertas = await chrome.tabs.query({ url: COMPRAS });
    if (abertas.length)
      await marcarSessao(
        "sem_sessao",
        "Abra o Compras.gov na área do fornecedor (a aba pública não tem a sessão)",
      );
    return null;
  }
  try {
    return await chrome.tabs.sendMessage(aba.id, { tipo: "executar", pedidos });
  } catch (erro) {
    await guardarUltimo(
      "ultimoErro",
      `Aba do Compras.gov não respondeu (aperte F5 nela): ${erro.message || erro}`,
    );
    return null;
  }
}

async function conferirSessao(resultados) {
  const falha = resultados.find(
    (r) => r.erro === "sem_sessao" || r.status === 401,
  );
  if (!falha) {
    if (resultados.some((r) => r.status >= 200 && r.status < 300))
      await marcarSessao("ok");
    return false;
  }
  if (falha.erro === "sem_sessao")
    await marcarSessao(
      "sem_sessao",
      "Aperte F5 na aba do Compras.gov (a Sentinela ainda não viu a sessão)",
    );
  else
    await marcarSessao(
      "sessao_caiu",
      "O Compras.gov pediu login de novo (401)",
    );
  return true;
}

// O que o Licita pediu (hoje: tirar o favorito de uma compra descartada).
async function fazerTarefas() {
  let tarefas;
  try {
    tarefas = await licita("tarefas/");
  } catch (erro) {
    await guardarUltimo("ultimoErro", String(erro.message || erro));
    return;
  }
  if (!tarefas.length) return;
  const pedidos = tarefas
    .filter((t) => t.tipo === "desfavoritar" && /^\d{17}$/.test(t.compra))
    .map((t) => ({
      id: t.id,
      metodo: "DELETE",
      caminho: `/comprasnet-oportunidade/v1/compras/${t.compra}/favorita`,
    }));
  const resposta = await executarNaAba(pedidos);
  if (!resposta) return; // sem aba: a tarefa espera
  if (await conferirSessao(resposta.resultados)) return;
  for (const r of resposta.resultados) {
    const ok = r.status >= 200 && r.status < 300;
    await licita(`tarefas/${r.id}/`, {
      method: "POST",
      body: JSON.stringify({
        ok,
        detalhe: ok
          ? "favorito tirado"
          : `Compras.gov respondeu ${r.status} ${r.erro || ""}`.trim(),
      }),
    }).catch(() => {});
  }
  await guardarUltimo(
    "ultimaTarefa",
    `${resposta.resultados.length} favorito(s)`,
  );
}

function emHorarioDeTrabalho(agora = new Date()) {
  const dia = agora.getDay();
  const hora = agora.getHours();
  return dia >= 1 && dia <= 5 && hora >= 8 && hora < 19;
}

// A ronda: favoritos, proposta, recurso, diligências e as propostas de todos
// (só endereços sem captcha; a lista vem do Licita, `ronda/`). A resposta vai
// para o Licita como captura — a mesma leitura de quando o Carlinhos abre a tela.
async function fazerRonda(forcar = false) {
  if (!forcar && !emHorarioDeTrabalho()) return;
  let lista;
  try {
    lista = await licita("ronda/");
  } catch (erro) {
    await guardarUltimo("ultimoErro", String(erro.message || erro));
    return;
  }
  const pedidos = (lista.consultas || []).map((caminho) => ({
    metodo: "GET",
    caminho,
  }));
  if (!pedidos.length) {
    await guardarUltimo("ultimaRonda", "nada para conferir");
    return;
  }
  const resposta = await executarNaAba(pedidos);
  if (!resposta) {
    await guardarUltimo("ultimaRonda", "sem aba do Compras.gov aberta");
    return;
  }
  if (await conferirSessao(resposta.resultados)) return;
  let enviadas = 0;
  for (const r of resposta.resultados) {
    if ((r.status !== 200 && r.status !== 206) || r.dados === null) continue;
    await licita("captura/", {
      method: "POST",
      body: JSON.stringify({
        url: resposta.origem + r.caminho,
        dados: r.dados,
        versao: VERSAO,
      }),
    })
      .then(() => enviadas++)
      .catch((erro) =>
        guardarUltimo("ultimoErro", String(erro.message || erro)),
      );
  }
  await guardarUltimo(
    "ultimaRonda",
    `${enviadas} de ${pedidos.length} consultas`,
  );
}

function agendar() {
  chrome.alarms.create("vigia", { periodInMinutes: 3 });
  chrome.alarms.create("tarefas", { periodInMinutes: 1 });
  // A primeira ronda 1 minuto depois que o Chrome abre (09/11/2026): se o
  // computador ligou às 10h, a vigia do dia acontece às 10h, sem esperar.
  chrome.alarms.create("ronda", { delayInMinutes: 1, periodInMinutes: 10 });
}

chrome.runtime.onInstalled.addListener(agendar);
chrome.runtime.onStartup.addListener(agendar);
chrome.alarms.onAlarm.addListener((alarme) => {
  if (alarme.name === "vigia") vigiar();
  if (alarme.name === "tarefas") fazerTarefas();
  if (alarme.name === "ronda") fazerRonda();
});

// "Abrir" do Licita: abre a compra numa cópia da aba do Compras.gov que já
// está logada (a sessão do Compras.gov vale por aba). Sem aba logada, abre
// uma aba nova — aí o Compras.gov pede login, como antes.
async function abrirCompra(url) {
  const aba = await abaDoCompras();
  if (!aba) {
    await chrome.tabs.create({ url });
    return;
  }
  const copia = await chrome.tabs.duplicate(aba.id);
  await chrome.tabs.update(copia.id, { url, active: true });
  if (copia.windowId !== undefined)
    await chrome.windows.update(copia.windowId, { focused: true });
}

async function abaDoCompras({ soLogada = false } = {}) {
  const abas = await chrome.tabs.query({ url: COMPRAS });
  // Prefere a aba logada (área do fornecedor).
  const logada = abas.find((a) => (a.url || "").includes("/seguro/"));
  if (soLogada) return logada || null;
  return logada || abas[0] || null;
}

chrome.runtime.onMessage.addListener((mensagem, _remetente, responder) => {
  if (mensagem.tipo === "abrir_compra") {
    abrirCompra(mensagem.url).catch((erro) =>
      guardarUltimo("ultimoErro", String(erro.message || erro)),
    );
    return false;
  }
  if (mensagem.tipo === "captura") {
    // A página leu um dado da área logada: a sessão está viva.
    marcarSessao("ok");
    licita("captura/", {
      method: "POST",
      body: JSON.stringify({
        url: mensagem.url,
        dados: mensagem.dados,
        versao: VERSAO,
      }),
    })
      .then((resumo) => guardarUltimo("ultimaCaptura", resumo))
      .catch((erro) =>
        guardarUltimo("ultimoErro", String(erro.message || erro)),
      );
    return false;
  }
  if (mensagem.tipo === "estado") {
    if (mensagem.estado === "sessao_caiu")
      marcarSessao("sessao_caiu", mensagem.detalhe || "");
    else pulso(mensagem.estado, mensagem.detalhe || "");
    return false;
  }
  if (mensagem.tipo === "camada") {
    licita(`camada/${mensagem.codigo}/`)
      .then((numeros) => responder({ ok: true, numeros }))
      .catch((erro) =>
        responder({ ok: false, erro: String(erro.message || erro) }),
      );
    return true; // resposta assíncrona
  }
  if (mensagem.tipo === "ronda_agora") {
    Promise.all([fazerTarefas(), fazerRonda(true)])
      .then(() =>
        chrome.storage.local.get(["ultimaRonda", "ultimaTarefa", "ultimoErro"]),
      )
      .then((estado) => responder(estado));
    return true;
  }
  if (mensagem.tipo === "testar") {
    vigiar()
      .then(() => chrome.storage.local.get(["ultimoPulso", "ultimoErro"]))
      .then((estado) => responder(estado));
    return true;
  }
  return false;
});
