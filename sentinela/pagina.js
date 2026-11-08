// Roda DENTRO da página do Compras.gov.br (mundo "MAIN").
//
// Só observa: quando a própria página recebe a resposta de uma destas
// consultas, copia a resposta e entrega para a ponte (ponte.js). Não faz
// nenhuma consulta, não toca em captcha, não lê senha nem token.
(() => {
  "use strict";

  const INTERESSA = [
    /\/comprasnet-fase-externa\/v1\/compras\/participacoes\/?$/,
    /\/comprasnet-fase-externa\/v1\/compras\/\d{17}\/participacao\/?$/,
    /\/comprasnet-fase-externa\/v1\/compras\/\d{17}\/itens\/em-selecao-fornecedores\/?$/,
    /\/comprasnet-fase-externa\/v1\/compras\/\d{17}\/em-selecao-fornecedores\/participacoes\/\d{14}\/itens\/[^/]+\/propostas\/?$/,
  ];
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
})();
