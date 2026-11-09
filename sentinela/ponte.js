// A ponte entre a página (pagina.js) e o fundo da extensão (fundo.js).
// Só aceita mensagens da própria aba, marcadas pela Sentinela.

// Depois de atualizar a extensão, a ponte das abas já abertas perde a ligação
// com ela: não manda nada (sem erro) até o F5.
function mandar(mensagem) {
  if (typeof chrome === "undefined" || !chrome.runtime || !chrome.runtime.id) return;
  try {
    chrome.runtime.sendMessage(mensagem);
  } catch {
    // extensão atualizada: esta aba precisa de F5
  }
}

const esperando = new Map();
let proximo = 1;

window.addEventListener("message", (evento) => {
  if (evento.source !== window || evento.origin !== location.origin) return;
  const mensagem = evento.data;
  if (!mensagem || mensagem.sentinela !== true) return;
  if (mensagem.tipo === "captura") {
    mandar({
      tipo: "captura",
      url: mensagem.url,
      dados: mensagem.dados,
    });
  } else if (mensagem.tipo === "estado") {
    mandar({
      tipo: "estado",
      estado: mensagem.estado,
      detalhe: mensagem.detalhe,
    });
  } else if (mensagem.tipo === "resposta" && esperando.has(mensagem.id)) {
    esperando.get(mensagem.id)(mensagem);
    esperando.delete(mensagem.id);
  }
});

// Uma consulta feita pela página (pagina.js), com a sessão dela.
function pedirAPagina(metodo, caminho) {
  const id = `s${proximo++}`;
  return new Promise((resolver) => {
    const limite = setTimeout(() => {
      esperando.delete(id);
      resolver({ status: 0, erro: "sem resposta da página" });
    }, 20000);
    esperando.set(id, (resposta) => {
      clearTimeout(limite);
      resolver(resposta);
    });
    window.postMessage(
      { sentinela: true, tipo: "pedido", id, metodo, caminho },
      location.origin,
    );
  });
}

const pausa = (ms) => new Promise((r) => setTimeout(r, ms));

// O fundo pede uma lista de consultas; elas vão uma de cada vez, com pausa
// (ritmo de gente, nada de rajada).
chrome.runtime.onMessage.addListener((mensagem, _remetente, responder) => {
  if (mensagem.tipo !== "executar") return false;
  (async () => {
    const resultados = [];
    for (const pedido of mensagem.pedidos) {
      const resposta = await pedirAPagina(pedido.metodo, pedido.caminho);
      // O id da resposta é o da conversa com a página; o do pedido (a tarefa
      // do Licita) é o que vale.
      const { id: _conversa, sentinela: _s, tipo: _t, ...resultado } = resposta;
      resultados.push({ ...pedido, ...resultado });
      if (resposta.erro === "sem_sessao" || resposta.status === 401) break;
      await pausa(1500);
    }
    responder({ origem: location.origin, resultados });
  })();
  return true;
});
