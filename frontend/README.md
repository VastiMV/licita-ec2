# Frontend

Angular 22 (standalone, zoneless), consumidor da API Django/DRF em
`docs/ARQUITETURA.md` (raiz do repositório). Ver [`docs/ARQUITETURA.md`](../docs/ARQUITETURA.md)
para o desenho geral e [`docs/DOMINIO.md`](../docs/DOMINIO.md) para o domínio
de negócio.

## Rodando localmente

```bash
npm install
npm start        # ng serve — http://localhost:4200, com proxy de /api para o backend local (proxy.conf.json)
npm test         # ng test — Vitest, roda uma vez (sem watch em CI; watch é o padrão local)
npm run build    # ng build — build de produção em dist/frontend
```

`proxy.conf.json` encaminha `/api` para `http://localhost:8000` (backend
Django local). Ajuste o `target` se o backend rodar em outra porta.

## Estrutura

```
src/
  styles/               tokens de design (cor, tipografia, espaçamento) e mixins SCSS
  app/
    core/
      api/               ApiClient (wrapper único do HttpClient) e ENDPOINTS (rotas centralizadas)
      auth/               AuthService, authInterceptor, authGuard — ver "Autenticação" em docs/ARQUITETURA.md
    contracts/            interfaces *Request/*Response por domínio — o formato exato da API
    services/             um serviço por domínio, só fala com a API via ApiClient + contracts
    shared/
      ui/                 átomos reutilizáveis: input-text, input-number (vírgula decimal,
                           prefixo/sufixo), select, date-picker, checkbox, button, badge,
                           icon, data-table (tabela com busca/ordenação/paginação integradas
                           ao endpoint) e toast (avisos flutuantes)
      overlay/             modal-shell + aviso-modal + question-modal, abertos via ModalService
    layout/shell/          menu + topo + router-outlet + rodapé (identidade Inside Solutions)
    layout/sidebar/        o menu azul escuro: Buscar, a Torre com as 13 etapas e o número de
                           licitações em cada uma (contagem-do-menu.service.ts), saídas, Cadastros
    layout/topo-status/    o topo: empresa e CNPJ, Radar, Sentinela e sino (estado verdadeiro)
    pages/                 uma pasta por tela, monta átomos/modais/serviços — não redeclara nada deles
      torre/               a Torre de Controle, TELA INICIAL: o quadro (4 estágios), estagio/
                           (um estágio aberto), etapa/ (lista da etapa), torre-cartao/ (o
                           cartão), torre.utils.ts (as frases do cartão) e
                           torre-acoes.service.ts (o que o clique abre) — ver docs/TORRE.md
      oportunidades/       pesquisar/ (busca ao vivo) + salvas/ (lista da equipe) e o
                           edital-card/ que as duas compartilham; cotador-modal/ é o
                           Cotador (fórmulas em cotador.model.ts, funções puras)
      ciclo/               o que a Torre usa do Ciclo antigo: cotador/, propostas/,
                           encerradas/ (com o processo-modal/ que mostra a história) e
                           descartadas/. quadro/ é o quadro antigo, sem rota (sai em
                           feat-remover-legado)
      empresas/, fornecedores/, produtos/   os cadastros
      configuracoes/       armazenamento/ e usuarios/ (só administrador)
      auth/login/          login (a única tela fora do shell)
    layout/brand/          a marca (logo) — único lugar que desenha o logo; as
                           imagens ficam em public/marca/ e o fundo escuro do logo
                           é o token --color-marca-fundo
```

**Regra de organização:** um único componente por tipo de controle/modal —
nenhuma página escreve seu próprio `<input>`, `<select>` ou diálogo. Estilo
segue a mesma lógica: tokens em `src/styles/`, cada átomo consome os tokens
via CSS custom properties/mixins, nunca redeclara uma cor ou espaçamento.

## Testes

Todo componente/serviço reutilizável tem `*.spec.ts` ao lado do arquivo
(Vitest, builder nativo do Angular CLI — `unit-test`/`ng test`). Ver
"Estratégia de testes" em `docs/ARQUITETURA.md`: teste vem antes do código.

**Nota para quem escrever novos testes:** o app é zoneless (sem `zone.js`).
Mutar um campo comum de um componente de teste (`host.valor = 'x'`) **não**
notifica o Angular para re-renderizar — use `signal()` para qualquer estado
de teste que precise refletir no DOM após um `fixture.detectChanges()`
subsequente. E quando o valor passa por `NgModel` (`[ngModel]`/`[(ngModel)]`),
o `writeValue` do `ControlValueAccessor` é aplicado num microtask — depois de
mudar o signal e chamar `detectChanges()`, dê `await fixture.whenStable()`
antes de checar o DOM. Exemplos: `shared/ui/input-text/input-text.component.spec.ts`,
`shared/ui/select/select.component.spec.ts`.
