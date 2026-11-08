// A ponte entre a página (pagina.js) e o fundo da extensão (fundo.js).
// Só aceita mensagens da própria aba, marcadas pela Sentinela.
window.addEventListener("message", (evento) => {
  if (evento.source !== window || evento.origin !== location.origin) return;
  const mensagem = evento.data;
  if (!mensagem || mensagem.sentinela !== true) return;
  if (mensagem.tipo === "captura") {
    chrome.runtime.sendMessage({
      tipo: "captura",
      url: mensagem.url,
      dados: mensagem.dados,
    });
  } else if (mensagem.tipo === "estado") {
    chrome.runtime.sendMessage({
      tipo: "estado",
      estado: mensagem.estado,
      detalhe: mensagem.detalhe,
    });
  }
});
