/**
 * Abre a compra no Compras.gov. A sessão de lá vale **por aba**: uma aba nova
 * cai no login. Com a Sentinela no Chrome (ela marca a página com
 * `data-sentinela`), quem abre é ela, numa cópia da aba já logada — a aba
 * original não é tocada. Sem Sentinela, aba nova como antes.
 */
export function abrirNoCompras(url: string): void {
  if (document.documentElement.dataset['sentinela']) {
    window.postMessage({ licita: true, tipo: 'abrir_no_compras', url }, location.origin);
    return;
  }
  window.open(url, '_blank', 'noopener');
}
