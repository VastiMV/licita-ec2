// Roda nas páginas do Licita (não no Compras.gov).
//
// O Compras.gov guarda a sessão POR ABA: uma aba nova aberta pelo Licita cai
// no login. Esta ponte deixa o Licita pedir à Sentinela para abrir a compra
// numa CÓPIA da aba do Compras.gov que já está logada (a cópia leva a sessão).
// A aba original não é tocada (ele pode estar no meio de uma disputa).
(() => {
  "use strict";
  // Avisa o Licita que a Sentinela está aqui (o Licita lê na hora do clique,
  // sem esperar: assim o navegador não bloqueia a aba nova quando não houver).
  document.documentElement.dataset.sentinela =
    chrome.runtime.getManifest().version;

  window.addEventListener("message", (evento) => {
    if (evento.source !== window || evento.origin !== location.origin) return;
    const m = evento.data;
    if (!m || m.licita !== true || m.tipo !== "abrir_no_compras") return;
    if (
      typeof m.url !== "string" ||
      !m.url.startsWith("https://cnetmobile.estaleiro.serpro.gov.br/")
    )
      return;
    if (!chrome.runtime || !chrome.runtime.id) return; // extensão atualizada: F5
    try {
      chrome.runtime.sendMessage({ tipo: "abrir_compra", url: m.url });
    } catch {
      // extensão atualizada: esta aba precisa de F5
    }
  });
})();
