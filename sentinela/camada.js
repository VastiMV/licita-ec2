// A camada de disputa: um painel no canto da tela do Compras.gov.br com os
// números da cotação do Licita para a compra aberta — teto, ideal, piso,
// custo e lucro de cada item. Só mostra; nunca preenche nem envia nada.
//
// 0.2.5 (GEN-61, 11/11/2026): o painel pode ser **arrastado** pela faixa do
// topo (a posição fica guardada neste Chrome) e **minimizado**: vira uma
// etiqueta "Cotador", da mesma cor, que abre de novo com um clique. Fechar e
// minimizar são a mesma coisa (decisão da operação).
(() => {
  "use strict";

  const CODIGO = /(?:compra=|\/)(\d{17})(?:[/?&#]|$)/;
  const CHAVE_POSICAO = "camadaPosicao";
  const MARGEM = 8; // px: o painel nunca sai da janela
  const ARRASTO_MINIMO = 4; // px: menos que isso é clique, não arrasto
  let codigoAtual = null;
  let painel = null;
  let minimizado = false;

  const moeda = (valor) =>
    valor === null || valor === undefined || valor === ""
      ? "—"
      : Number(valor).toLocaleString("pt-BR", {
          style: "currency",
          currency: "BRL",
        });

  function el(tag, classe, texto) {
    const no = document.createElement(tag);
    if (classe) no.className = classe;
    if (texto !== undefined) no.textContent = texto;
    return no;
  }

  function nomeDaCompra(codigo) {
    const modalidades = {
      "05": "Pregão",
      "06": "Dispensa",
      "07": "Inexigibilidade",
      "03": "Concorrência",
    };
    const modalidade = modalidades[codigo.slice(6, 8)] || "Compra";
    return `${modalidade} ${Number(codigo.slice(8, 13))}/${codigo.slice(13)}`;
  }

  function montarPainel() {
    painel = el("aside", "sentinela-camada");
    painel.setAttribute("aria-label", "Sentinela: números da cotação");
    const topo = el("div", "sentinela-topo");
    topo.title = "Arraste para mudar o painel de lugar";
    const titulo = el("strong", "sentinela-titulo", "Sentinela");
    const minimizar = el("button", "sentinela-recolher", "–");
    minimizar.type = "button";
    minimizar.title = "Minimizar";
    minimizar.setAttribute("aria-label", "Minimizar o painel");
    minimizar.addEventListener("click", () => alternar(true));
    // Atualizar agora: depois de mexer na cotação no Licita.
    const atualizar = el("button", "sentinela-recolher", "↻");
    atualizar.type = "button";
    atualizar.title = "Atualizar agora com a cotação do Licita";
    atualizar.setAttribute(
      "aria-label",
      "Atualizar agora com a cotação do Licita",
    );
    atualizar.addEventListener(
      "click",
      () => codigoAtual && carregar(codigoAtual),
    );
    const botoes = el("div", "sentinela-botoes");
    botoes.append(atualizar, minimizar);
    topo.append(titulo, botoes);
    // Minimizado, o painel é só esta etiqueta. Também dá para arrastar.
    const etiqueta = el("button", "sentinela-etiqueta", "Cotador");
    etiqueta.type = "button";
    etiqueta.title = "Abrir o painel do Cotador (arraste para mudar de lugar)";
    etiqueta.setAttribute("aria-label", "Abrir o painel do Cotador");
    etiqueta.addEventListener("click", () => {
      if (!arrastou) alternar(false);
    });
    painel.append(
      etiqueta,
      topo,
      el("div", "sentinela-corpo"),
      el("p", "sentinela-hora", ""),
    );
    document.body.append(painel);
    arrastavel(topo);
    arrastavel(etiqueta);
    painel.classList.toggle("sentinela-minimizado", minimizado);
    restaurarPosicao();
    window.addEventListener("resize", () => {
      const r = painel.getBoundingClientRect();
      if (painel.style.left) posicionar(r.left, r.top);
    });
  }

  function alternar(minimizar) {
    minimizado = minimizar;
    painel.classList.toggle("sentinela-minimizado", minimizado);
    // Mudou de tamanho: continua inteiro dentro da janela.
    if (painel.style.left) {
      const r = painel.getBoundingClientRect();
      posicionar(r.left, r.top);
    }
  }

  // ---- arrastar ----------------------------------------------------------

  let arrastou = false;

  function arrastavel(alca) {
    alca.addEventListener("pointerdown", (evento) => {
      if (evento.button !== 0) return;
      // Os botões do topo continuam sendo botões.
      if (
        alca !== evento.target.closest(".sentinela-etiqueta, .sentinela-topo")
      )
        return;
      if (evento.target.closest(".sentinela-botoes")) return;
      const inicio = painel.getBoundingClientRect();
      const x0 = evento.clientX;
      const y0 = evento.clientY;
      arrastou = false;
      alca.setPointerCapture(evento.pointerId);

      const mover = (e) => {
        const dx = e.clientX - x0;
        const dy = e.clientY - y0;
        if (!arrastou && Math.hypot(dx, dy) < ARRASTO_MINIMO) return;
        arrastou = true;
        painel.classList.add("sentinela-arrastando");
        posicionar(inicio.left + dx, inicio.top + dy);
      };
      const soltar = () => {
        alca.removeEventListener("pointermove", mover);
        alca.removeEventListener("pointerup", soltar);
        alca.removeEventListener("pointercancel", soltar);
        painel.classList.remove("sentinela-arrastando");
        if (arrastou) guardarPosicao();
      };
      alca.addEventListener("pointermove", mover);
      alca.addEventListener("pointerup", soltar);
      alca.addEventListener("pointercancel", soltar);
    });
  }

  function posicionar(esquerda, topo) {
    const r = painel.getBoundingClientRect();
    const maxX = Math.max(MARGEM, window.innerWidth - r.width - MARGEM);
    const maxY = Math.max(MARGEM, window.innerHeight - r.height - MARGEM);
    painel.style.left = `${Math.min(Math.max(esquerda, MARGEM), maxX)}px`;
    painel.style.top = `${Math.min(Math.max(topo, MARGEM), maxY)}px`;
    painel.style.right = "auto";
    painel.style.bottom = "auto";
  }

  // A posição fica neste Chrome (storage da extensão), não no Licita.
  function guardarPosicao() {
    if (!viva()) return;
    const r = painel.getBoundingClientRect();
    chrome.storage.local
      .set({ [CHAVE_POSICAO]: { esquerda: r.left, topo: r.top } })
      .catch(() => {});
  }

  function restaurarPosicao() {
    if (!viva()) return;
    chrome.storage.local
      .get(CHAVE_POSICAO)
      .then((guardado) => {
        const p = guardado && guardado[CHAVE_POSICAO];
        if (p && Number.isFinite(p.esquerda) && Number.isFinite(p.topo))
          posicionar(p.esquerda, p.topo);
      })
      .catch(() => {});
  }

  function mostrar(conteudo, subtitulo) {
    if (!painel) montarPainel();
    painel.querySelector(".sentinela-titulo").textContent =
      `Sentinela · ${subtitulo}`;
    const corpo = painel.querySelector(".sentinela-corpo");
    corpo.replaceChildren(conteudo);
    // Para ele saber se o número é recente (a cotação pode ter mudado no Licita).
    painel.querySelector(".sentinela-hora").textContent =
      `Atualizado às ${new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}`;
    painel.hidden = false;
  }

  function tabela(itens) {
    const tabela = el("table", "sentinela-tabela");
    const cabeca = el("tr");
    ["Item", "Teto", "Ideal", "Piso", "Custo", "Lucro"].forEach((t) =>
      cabeca.append(el("th", "", t)),
    );
    const cabecalho = el("thead");
    cabecalho.append(cabeca);
    tabela.append(cabecalho);
    const corpo = el("tbody");
    itens.forEach((item) => {
      const linha = el("tr");
      linha.title = item.descricao || "";
      linha.append(
        el("td", "sentinela-item", item.numero || "—"),
        el("td", "", moeda(item.teto)),
        el("td", "sentinela-ideal", moeda(item.ideal)),
        el("td", "sentinela-piso", moeda(item.piso)),
        el("td", "", moeda(item.custo)),
        el("td", "", moeda(item.lucro_no_ideal)),
      );
      if (item.incompleto) linha.classList.add("sentinela-incompleto");
      const teto = Number(item.teto);
      if (item.teto && Number(item.piso) > teto) {
        linha.classList.add("sentinela-impossivel");
        linha.title = `Piso acima do teto: nem o lance mínimo cabe no valor de referência. ${linha.title}`;
      } else if (item.teto && Number(item.ideal) > teto) {
        linha.classList.add("sentinela-acima");
        linha.title = `Ideal acima do teto: o lance terá de ficar entre o piso e o teto. ${linha.title}`;
      }
      corpo.append(linha);
    });
    tabela.append(corpo);
    const legenda = el(
      "p",
      "sentinela-legenda",
      "Piso = o menor lance que ainda dá lucro mínimo. Amarelo: ideal acima do teto. Vermelho: nem o piso cabe no teto. Valores por unidade, da cotação do Licita.",
    );
    const bloco = el("div");
    bloco.append(tabela, legenda);
    return bloco;
  }

  // Depois de atualizar a extensão, o painel das abas já abertas perde a
  // ligação com ela (chrome.runtime some): ele para quieto até o F5.
  function viva() {
    return typeof chrome !== "undefined" && !!(chrome.runtime && chrome.runtime.id);
  }

  function carregar(codigo) {
    if (!viva()) return;
    chrome.runtime.sendMessage({ tipo: "camada", codigo }, (resposta) => {
      if (codigo !== codigoAtual) return;
      const nome = nomeDaCompra(codigo);
      if (!resposta || !resposta.ok) {
        mostrar(
          el(
            "p",
            "sentinela-aviso",
            `Sem conexão com o Licita. ${resposta ? resposta.erro : ""}`,
          ),
          nome,
        );
      } else if (!resposta.numeros.conhecida) {
        mostrar(
          el("p", "sentinela-aviso", "Esta compra não está no Licita."),
          nome,
        );
      } else if (
        !resposta.numeros.tem_cotacao ||
        !resposta.numeros.itens.length
      ) {
        mostrar(
          el("p", "sentinela-aviso", "Sem cotação no Licita para esta compra."),
          nome,
        );
      } else {
        mostrar(tabela(resposta.numeros.itens), nome);
      }
    });
  }

  function verificar() {
    if (!viva()) {
      clearInterval(relogio);
      return;
    }
    const achado = location.href.match(CODIGO);
    const codigo = achado ? achado[1] : null;
    if (codigo === codigoAtual) return;
    codigoAtual = codigo;
    if (!codigo) {
      if (painel) painel.hidden = true;
      return;
    }
    carregar(codigo);
  }

  let relogio = null;

  function iniciar() {
    verificar();
    // O Compras.gov é uma página só: o endereço muda sem recarregar.
    relogio = setInterval(verificar, 1500);
    // A cotação é lida ao abrir a compra e no F5 (pedido da operação,
    // 08/11/2026: não precisa conferir a cada minuto). O ↻ lê na hora.
  }

  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", iniciar);
  else iniciar();
})();
