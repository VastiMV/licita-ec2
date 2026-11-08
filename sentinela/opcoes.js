const campos = ["licita", "chave"];
const estado = document.getElementById("estado");

function quando(registro) {
  if (!registro) return "nunca";
  return new Date(registro.em).toLocaleString("pt-BR");
}

async function mostrarEstado() {
  const s = await chrome.storage.local.get([
    "ultimoPulso",
    "ultimaCaptura",
    "ultimoErro",
  ]);
  estado.textContent = [
    `Último sinal de vida: ${quando(s.ultimoPulso)}${s.ultimoPulso ? ` (${s.ultimoPulso.valor})` : ""}`,
    `Última leitura enviada: ${quando(s.ultimaCaptura)}${s.ultimaCaptura ? ` (${JSON.stringify(s.ultimaCaptura.valor)})` : ""}`,
    `Último erro: ${s.ultimoErro ? `${quando(s.ultimoErro)} — ${s.ultimoErro.valor}` : "nenhum"}`,
  ].join("\n");
}

async function carregar() {
  const salvo = await chrome.storage.local.get({
    licita: "https://insidelicitacoes.com.br",
    chave: "",
  });
  campos.forEach((c) => (document.getElementById(c).value = salvo[c] || ""));
  mostrarEstado();
}

document.getElementById("salvar").addEventListener("click", async () => {
  const valores = Object.fromEntries(
    campos.map((c) => [c, document.getElementById(c).value.trim()]),
  );
  await chrome.storage.local.set(valores);
  estado.textContent = "Salvo.";
});

document.getElementById("testar").addEventListener("click", async () => {
  estado.textContent = "Testando…";
  await chrome.storage.local.remove("ultimoErro");
  await chrome.runtime.sendMessage({ tipo: "testar" });
  mostrarEstado();
});

carregar();
