// O fundo da Sentinela: manda ao Licita o que a página capturou e, a cada
// 3 minutos, o sinal de vida (o "vigia" do topo do Licita).
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
async function vigiar() {
  const abas = await chrome.tabs.query({ url: COMPRAS });
  await pulso(
    abas.length ? "ok" : "sem_aba",
    abas.length ? "" : "Nenhuma aba do Compras.gov aberta",
  );
}

// -- consultas feitas na aba do Compras.gov (com a sessão da página) ---------

async function abaDoCompras() {
  const abas = await chrome.tabs.query({ url: COMPRAS });
  return abas[0] || null;
}

// Manda à aba uma lista de consultas; ela faz uma de cada vez, com pausa.
async function executarNaAba(pedidos) {
  const aba = await abaDoCompras();
  if (!aba) return null;
  try {
    return await chrome.tabs.sendMessage(aba.id, { tipo: "executar", pedidos });
  } catch (erro) {
    await guardarUltimo(
      "ultimoErro",
      `Aba do Compras.gov não respondeu: ${erro.message || erro}`,
    );
    return null;
  }
}

function avisarSeASessaoCaiu(resultados) {
  const falha = resultados.find(
    (r) => r.erro === "sem_sessao" || r.status === 401,
  );
  if (!falha) return false;
  const detalhe =
    falha.erro === "sem_sessao"
      ? "Abra ou atualize a aba do Compras.gov (a Sentinela ainda não viu a sessão)"
      : "O Compras.gov pediu login de novo";
  pulso("sessao_caiu", detalhe);
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
  if (avisarSeASessaoCaiu(resposta.resultados)) return;
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
  return dia >= 1 && dia <= 5 && hora >= 8 && hora < 18;
}

// A ronda: proposta, fase recursal e diligências de cada item com proposta
// (só endereços sem captcha). A resposta vai para o Licita como captura.
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
  if (avisarSeASessaoCaiu(resposta.resultados)) return;
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
  chrome.alarms.create("ronda", { periodInMinutes: 10 });
}

chrome.runtime.onInstalled.addListener(agendar);
chrome.runtime.onStartup.addListener(agendar);
chrome.alarms.onAlarm.addListener((alarme) => {
  if (alarme.name === "vigia") vigiar();
  if (alarme.name === "tarefas") fazerTarefas();
  if (alarme.name === "ronda") fazerRonda();
});

chrome.runtime.onMessage.addListener((mensagem, _remetente, responder) => {
  if (mensagem.tipo === "captura") {
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
    pulso(mensagem.estado, mensagem.detalhe || "");
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
