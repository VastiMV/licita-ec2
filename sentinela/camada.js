// A camada de disputa: um painel no canto da tela do Compras.gov.br com os
// números da cotação do Licita para a compra aberta — teto, ideal, piso,
// custo e lucro de cada item. Só mostra; nunca preenche nem envia nada.
(() => {
  "use strict";

  const CODIGO = /(?:compra=|\/)(\d{17})(?:[/?&#]|$)/;
  let codigoAtual = null;
  let painel = null;
  let recolhido = false;

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
    const titulo = el("strong", "sentinela-titulo", "Sentinela");
    const botao = el("button", "sentinela-recolher", "–");
    botao.type = "button";
    botao.setAttribute("aria-label", "Recolher ou abrir o painel");
    botao.addEventListener("click", () => {
      recolhido = !recolhido;
      painel.classList.toggle("sentinela-recolhido", recolhido);
      botao.textContent = recolhido ? "+" : "–";
    });
    topo.append(titulo, botao);
    painel.append(topo, el("div", "sentinela-corpo"));
    document.body.append(painel);
  }

  function mostrar(conteudo, subtitulo) {
    if (!painel) montarPainel();
    painel.querySelector(".sentinela-titulo").textContent =
      `Sentinela · ${subtitulo}`;
    const corpo = painel.querySelector(".sentinela-corpo");
    corpo.replaceChildren(conteudo);
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

  function carregar(codigo) {
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

  function iniciar() {
    verificar();
    // O Compras.gov é uma página só: o endereço muda sem recarregar.
    setInterval(verificar, 1500);
  }

  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", iniciar);
  else iniciar();
})();
