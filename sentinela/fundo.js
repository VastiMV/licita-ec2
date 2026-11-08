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

chrome.runtime.onInstalled.addListener(() => {
  chrome.alarms.create("vigia", { periodInMinutes: 3 });
});
chrome.runtime.onStartup.addListener(() => {
  chrome.alarms.create("vigia", { periodInMinutes: 3 });
});
chrome.alarms.onAlarm.addListener((alarme) => {
  if (alarme.name === "vigia") vigiar();
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

async function abaDoCompras() {
  const abas = await chrome.tabs.query({ url: COMPRAS });
  // Prefere a aba logada (área do fornecedor).
  return (
    abas.find((a) => (a.url || "").includes("/seguro/")) || abas[0] || null
  );
}

chrome.runtime.onMessage.addListener((mensagem, _remetente, responder) => {
  if (mensagem.tipo === "abrir_compra") {
    abrirCompra(mensagem.url).catch((erro) =>
      guardarUltimo("ultimoErro", String(erro.message || erro)),
    );
    return false;
  }
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
  if (mensagem.tipo === "testar") {
    vigiar()
      .then(() => chrome.storage.local.get(["ultimoPulso", "ultimoErro"]))
      .then((estado) => responder(estado));
    return true;
  }
  return false;
});
