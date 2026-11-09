// Roda DENTRO da página do Compras.gov.br (mundo "MAIN").
//
// 1. OBSERVA: quando a própria página recebe a resposta de uma destas
//    consultas, copia a resposta e entrega para a ponte (ponte.js).
// 2. LEMBRA A SESSÃO: quando a página manda o cabeçalho `authorization`,
//    guarda o valor numa variável desta função — só na memória desta aba.
//    Nunca é gravado, nunca sai do computador, nunca vai para o Licita.
// 3. CONSULTA SOZINHA, a pedido da ponte, só o que está em PERMITIDO: a
//    lista de propostas de um item, que NÃO pede captcha. Só leitura (GET).
//    Nunca toca em tela com captcha.
(() => {
  "use strict";

  const INTERESSA = [
    /\/comprasnet-fase-externa\/v1\/compras\/participacoes\/?$/,
    /\/comprasnet-fase-externa\/v1\/compras\/\d{17}\/participacao\/?$/,
    /\/comprasnet-fase-externa\/v1\/compras\/\d{17}\/itens\/em-selecao-fornecedores\/?$/,
    /\/comprasnet-fase-externa\/v1\/compras\/\d{17}\/em-selecao-fornecedores\/participacoes\/\d{14}\/itens\/[^/]+\/propostas\/?$/,
    /\/comprasnet-fase-externa\/v1\/compras\/\d{17}\/em-selecao-fornecedores\/itens\/[^/]+\/propostas\/?$/,
  ];

  // O que a Sentinela pode consultar sozinha: só leitura, sem captcha.
  const PERMITIDO = [
    {
      metodo: "GET",
      padrao:
        /^\/comprasnet-fase-externa\/v1\/compras\/\d{17}\/em-selecao-fornecedores\/itens\/[A-Za-z0-9-]+\/propostas\?ordenacao-propostas=V$/,
    },
  ];

  // A sessão da aba, como a página a usa. Só na memória.
  const sessao = { authorization: "", versao: "" };

  function lembrar(nome, valor) {
    const n = String(nome || "").toLowerCase();
    if (n === "authorization" && /^Bearer\s+\S+/.test(String(valor)))
      sessao.authorization = String(valor);
    if (n === "x-version-number" && valor) sessao.versao = String(valor);
  }

  function lembrarCabecalhos(cabecalhos) {
    if (!cabecalhos) return;
    if (typeof Headers !== "undefined" && cabecalhos instanceof Headers) {
      cabecalhos.forEach((valor, nome) => lembrar(nome, valor));
    } else if (Array.isArray(cabecalhos)) {
      cabecalhos.forEach(([nome, valor]) => lembrar(nome, valor));
    } else if (typeof cabecalhos === "object") {
      Object.entries(cabecalhos).forEach(([nome, valor]) =>
        lembrar(nome, valor),
      );
    }
  }
  const RETOKEN = /\/comprasnet-usuario\/v2\/sessao\/fornecedor\/retoken\/?$/;

  function endereco(url) {
    try {
      return new URL(url, location.href);
    } catch {
      return null;
    }
  }

  function entregar(mensagem) {
    window.postMessage({ sentinela: true, ...mensagem }, location.origin);
  }

  // Tira o captcha do endereço antes de mandar: o Licita não precisa dele.
  function semCaptcha(u) {
    const limpo = new URL(u.href);
    limpo.searchParams.delete("captcha");
    return limpo.href;
  }

  function observar(url, status, lerTexto) {
    const u = endereco(url);
    if (!u) return;
    if (RETOKEN.test(u.pathname) && status >= 400) {
      entregar({
        tipo: "estado",
        estado: "sessao_caiu",
        detalhe: `retoken ${status}`,
      });
      return;
    }
    if (status !== 200 && status !== 206) return;
    if (!INTERESSA.some((padrao) => padrao.test(u.pathname))) return;
    Promise.resolve()
      .then(lerTexto)
      .then((texto) =>
        entregar({
          tipo: "captura",
          url: semCaptcha(u),
          dados: JSON.parse(texto),
        }),
      )
      .catch(() => {});
  }

  const fetchOriginal = window.fetch;
  window.fetch = async function (...args) {
    try {
      const pedido = args[0];
      lembrarCabecalhos(args[1] && args[1].headers);
      if (pedido && typeof pedido === "object" && pedido.headers)
        lembrarCabecalhos(pedido.headers);
    } catch {
      // nunca atrapalhar a página
    }
    const resposta = await fetchOriginal.apply(this, args);
    try {
      const pedido = args[0];
      const url = typeof pedido === "string" ? pedido : pedido && pedido.url;
      const copia = resposta.clone();
      observar(url, resposta.status, () => copia.text());
    } catch {
      // nunca atrapalhar a página
    }
    return resposta;
  };

  const abrir = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function (metodo, url, ...resto) {
    this.__sentinelaUrl = url;
    return abrir.call(this, metodo, url, ...resto);
  };
  const definirCabecalho = XMLHttpRequest.prototype.setRequestHeader;
  XMLHttpRequest.prototype.setRequestHeader = function (nome, valor) {
    try {
      lembrar(nome, valor);
    } catch {
      // nunca atrapalhar a página
    }
    return definirCabecalho.call(this, nome, valor);
  };
  const enviar = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.send = function (...args) {
    this.addEventListener("load", () => {
      try {
        observar(this.__sentinelaUrl, this.status, () => {
          if (this.responseType === "" || this.responseType === "text")
            return this.responseText;
          if (this.responseType === "json")
            return JSON.stringify(this.response);
          throw new Error("formato não lido");
        });
      } catch {
        // nunca atrapalhar a página
      }
    });
    return enviar.apply(this, args);
  };

  // -- consultas da Sentinela (a pedido da ponte) -----------------------------

  async function executar(pedido) {
    const permitido = PERMITIDO.find(
      (p) => p.metodo === pedido.metodo && p.padrao.test(pedido.caminho),
    );
    if (!permitido)
      return { status: 0, erro: "endereço fora da lista permitida" };
    if (!sessao.authorization) return { status: 0, erro: "sem_sessao" };
    const resposta = await fetchOriginal.call(
      window,
      location.origin + pedido.caminho,
      {
        method: "GET",
        credentials: "same-origin",
        headers: {
          accept: "application/json, text/plain, */*",
          authorization: sessao.authorization,
          "x-device-platform": "web",
          "x-version-number": sessao.versao || "6.4.4",
        },
      },
    );
    if (resposta.status === 401) {
      sessao.authorization = "";
      entregar({
        tipo: "estado",
        estado: "sessao_caiu",
        detalhe: "O Compras.gov pediu login de novo (401)",
      });
    }
    const texto = await resposta.text().catch(() => "");
    let dados = null;
    try {
      dados = texto ? JSON.parse(texto) : null;
    } catch {
      dados = null;
    }
    return { status: resposta.status, dados };
  }

  window.addEventListener("message", (evento) => {
    if (evento.source !== window || evento.origin !== location.origin) return;
    const m = evento.data;
    if (!m || m.sentinela !== true || m.tipo !== "pedido") return;
    executar(m)
      .catch((erro) => ({
        status: 0,
        erro: String(erro && erro.message ? erro.message : erro),
      }))
      .then((resultado) =>
        entregar({ tipo: "resposta", id: m.id, ...resultado }),
      );
  });
})();
