import { Routes } from '@angular/router';

import { authGuard } from './core/auth/auth.guard';
import { ShellComponent } from './layout/shell/shell.component';

const CICLO = [
  {
    path: 'disputas',
    titulo: 'Disputas',
    descricao: 'As licitações em sessão, habilitação ou recurso, até a homologação.',
  },
  {
    path: 'empenhos',
    titulo: 'Empenhos',
    descricao: 'As licitações ganhas: ata ou contrato, notas de empenho e pedidos ao fornecedor.',
  },
];

export const routes: Routes = [
  // Independente de propósito — não é filha do Shell, não tem navbar/menu.
  {
    path: 'login',
    loadComponent: () => import('./pages/auth/login/login.page').then((m) => m.LoginPage),
  },
  {
    path: '',
    component: ShellComponent,
    // No Shell inteiro, não em cada filha — nenhuma rota atrás dele fica
    // aberta sem login (nova filha entra protegida sem precisar lembrar
    // de repetir `canActivate` nela).
    canActivate: [authGuard],
    children: [
      // A tela inicial é a Torre de Controle: é o que a operação abre
      // primeiro no dia (decisão de 08/11/2026).
      { path: '', pathMatch: 'full', redirectTo: 'torre' },
      // "Oportunidades" não é uma tela: quem abre é "Buscar" (a busca ao
      // vivo) ou "Salvas" (a lista que a equipe montou a partir dela).
      {
        path: 'oportunidades',
        children: [
          { path: '', pathMatch: 'full', redirectTo: 'buscar' },
          // O endereço antigo continua valendo para quem guardou o link.
          { path: 'pesquisar', redirectTo: 'buscar' },
          {
            path: 'buscar',
            loadComponent: () =>
              import('./pages/oportunidades/pesquisar/pesquisar.page').then((m) => m.PesquisarPage),
          },
          {
            path: 'salvas',
            loadComponent: () =>
              import('./pages/oportunidades/salvas/salvas.page').then((m) => m.SalvasPage),
          },
        ],
      },
      // A Torre de Controle: os 4 estágios, um estágio aberto e a lista de
      // cada etapa (ver apps/licitacoes/torre.py). Fica ao lado do Ciclo de
      // Licitação, que continua no ar até a Torre ser aprovada.
      {
        path: 'torre',
        children: [
          {
            path: '',
            pathMatch: 'full',
            loadComponent: () => import('./pages/torre/torre.page').then((m) => m.TorrePage),
          },
          {
            path: 'estagio/:estagio',
            loadComponent: () =>
              import('./pages/torre/estagio/estagio.page').then((m) => m.EstagioPage),
          },
          {
            path: 'etapa/:etapa',
            loadComponent: () => import('./pages/torre/etapa/etapa.page').then((m) => m.EtapaPage),
          },
        ],
      },
      // O que sobrou do Ciclo de Licitação e a Torre ainda usa: Cotador,
      // Propostas (PDF), Encerradas e Descartadas.
      {
        path: 'ciclo',
        children: [
          // O quadro antigo (Visão Geral) deu lugar à Torre de Controle em
          // 08/11/2026: link salvo para ele cai na Torre, para ninguém ver
          // duas verdades. O código antigo sai em feat-remover-legado.
          { path: '', pathMatch: 'full', redirectTo: '/torre' },
          { path: 'visao-geral', redirectTo: '/torre' },
          {
            path: 'cotador',
            loadComponent: () =>
              import('./pages/ciclo/cotador/cotador.page').then((m) => m.CotadorPage),
          },
          {
            path: 'propostas',
            loadComponent: () =>
              import('./pages/ciclo/propostas/propostas.page').then((m) => m.PropostasPage),
          },
          {
            path: 'encerradas',
            loadComponent: () =>
              import('./pages/ciclo/encerradas/encerradas.page').then((m) => m.EncerradasPage),
          },
          {
            path: 'descartadas',
            loadComponent: () =>
              import('./pages/ciclo/descartadas/descartadas.page').then((m) => m.DescartadasPage),
          },
          ...CICLO.map(({ path, titulo, descricao }) => ({
            path,
            pathMatch: 'full' as const,
            data: { titulo, descricao },
            loadComponent: () =>
              import('./pages/ciclo/etapa-a-construir/etapa-a-construir.page').then(
                (m) => m.EtapaAConstruirPage,
              ),
          })),
        ],
      },
      {
        path: 'empresas',
        loadComponent: () => import('./pages/empresas/empresas.page').then((m) => m.EmpresasPage),
      },
      {
        path: 'fornecedores',
        loadComponent: () =>
          import('./pages/fornecedores/fornecedores.page').then((m) => m.FornecedoresPage),
      },
      {
        path: 'produtos',
        loadComponent: () => import('./pages/produtos/produtos.page').then((m) => m.ProdutosPage),
      },
      // Configurações é menu de primeiro nível com filhos, como
      // Oportunidades — "Armazenamento" e "Usuários", só para o super usuário
      // (quem barra de verdade é o backend, com 403).
      {
        path: 'configuracoes',
        children: [
          { path: '', pathMatch: 'full', redirectTo: 'armazenamento' },
          {
            path: 'armazenamento',
            loadComponent: () =>
              import('./pages/configuracoes/armazenamento/armazenamento.page').then(
                (m) => m.ArmazenamentoPage,
              ),
          },
          {
            path: 'usuarios',
            loadComponent: () =>
              import('./pages/configuracoes/usuarios/usuarios.page').then((m) => m.UsuariosPage),
          },
        ],
      },
    ],
  },
  { path: '**', redirectTo: 'torre' },
];
