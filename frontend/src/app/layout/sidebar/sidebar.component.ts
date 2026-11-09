import { Component, computed, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterLink } from '@angular/router';
import { filter } from 'rxjs';

import { AuthService } from '../../core/auth/auth.service';
import { IconComponent, type IconName } from '../../shared/ui/icon/icon.component';
import { BrandComponent } from '../brand/brand.component';
import { NavGroupComponent, type NavSubItem } from '../nav-group/nav-group.component';
import { NavItemComponent } from '../nav-item/nav-item.component';
import { ContagemDoMenuService } from './contagem-do-menu.service';
import { SidebarStateService } from './sidebar-state.service';

/** Um link do menu. */
interface EntradaItem {
  readonly tipo: 'item';
  readonly path: string;
  readonly label: string;
  readonly icon: IconName;
  readonly exato?: boolean;
  /** O botão azul do topo ("Buscar oportunidades"). */
  readonly destaque?: boolean;
  /** Fica embaixo do item anterior (Descartadas, embaixo de Encerradas). */
  readonly recuo?: boolean;
}

/** Um estágio da Torre (ou os Cadastros): título fixo e as etapas embaixo,
 * sempre à vista — nada para abrir e fechar. */
interface EntradaSecao {
  readonly tipo: 'secao';
  readonly label: string;
  /** O título leva ao estágio aberto; sem `path`, é só título. */
  readonly path?: string;
  readonly itens: readonly NavSubItem[];
}

/** Grupo que abre e fecha (ver `NavGroupComponent`) — só Configurações. */
interface EntradaGrupo {
  readonly tipo: 'grupo';
  readonly label: string;
  readonly icon: IconName;
  readonly itens: readonly NavSubItem[];
}

interface EntradaLinha {
  readonly tipo: 'linha';
}

type Entrada = EntradaItem | EntradaSecao | EntradaGrupo | EntradaLinha;

/**
 * Menu lateral das páginas de módulo — marca + navegação. Substituiu a
 * antiga topbar de links horizontais (ver `NavbarComponent`, que agora só
 * tem o botão hamburguer e o menu de perfil).
 *
 * Em desktop fica sempre visível: expandida (marca + rótulos) por padrão,
 * ou recolhida a um trilho de ícones (`SidebarStateService.collapsed`) —
 * quem alterna é o botão de colapso aqui dentro. Em mobile vira um painel
 * off-canvas, escondido até o hamburguer da `Navbar` abrir
 * (`SidebarStateService.mobileOpen`); breakpoint em 640px pra ficar igual
 * ao resto do layout (ver `shell.component.scss`).
 *
 * Não é usada no login: essa página é independente, sem shell nenhuma.
 *
 * "Configurações" só aparece para o super usuário. Isso é cortesia, não
 * segurança: quem barra de verdade é o backend (`EhSuperusuario` em
 * `apps/accounts/permissions.py`) — aqui é só não oferecer o que a pessoa
 * não pode usar.
 */
@Component({
  selector: 'app-sidebar',
  imports: [BrandComponent, NavItemComponent, NavGroupComponent, IconComponent, RouterLink],
  templateUrl: './sidebar.component.html',
  styleUrl: './sidebar.component.scss',
})
export class SidebarComponent {
  protected readonly state = inject(SidebarStateService);
  private readonly auth = inject(AuthService);
  private readonly contagens = inject(ContagemDoMenuService);

  constructor() {
    // O número de cada etapa muda quando a operação mexe em algo: recontar
    // a cada troca de tela basta (é uma pessoa só usando).
    this.contagens.atualizar();
    inject(Router)
      .events.pipe(
        filter((evento) => evento instanceof NavigationEnd),
        takeUntilDestroyed(),
      )
      .subscribe(() => this.contagens.atualizar());
  }

  /** Quantas licitações há na etapa daquele endereço; `null` fora da Torre. */
  protected contagem(path: string): number | null {
    return this.contagens.porEndereco().get(path) ?? null;
  }

  /** Em mobile a Sidebar é um painel off-canvas: navegar fecha o painel.
   * Abrir/fechar um grupo (ver `NavGroupComponent`), não — o clique no
   * cabeçalho do grupo borbulha até aqui, mas não é navegação. */
  protected fecharSeNavegou(evento: Event): void {
    if ((evento.target as HTMLElement).closest('a')) this.state.closeMobile();
  }

  protected readonly entradas = computed<readonly Entrada[]>(() => [
    ...MENU,
    ...(this.auth.ehSuperusuario() ? [CONFIGURACOES] : []),
  ]);
}

const CONFIGURACOES: Entrada = {
  tipo: 'grupo',
  label: 'Configurações',
  icon: 'configuracoes',
  itens: [
    { path: '/configuracoes/armazenamento', label: 'Armazenamento', icon: 'armazenamento' },
    { path: '/configuracoes/usuarios', label: 'Usuários', icon: 'user' },
  ],
};

// Como no protótipo "Licita v1.0": Buscar no topo, a Torre com os 4 estágios
// sempre abertos (cada etapa com o número de licitações nela), as saídas e
// os Cadastros. Oportunidade e Cotação abrem as listas que já existiam.
const MENU: readonly Entrada[] = [
  {
    tipo: 'item',
    path: '/oportunidades/buscar',
    label: 'Buscar oportunidades',
    icon: 'search',
    destaque: true,
  },
  { tipo: 'item', path: '/torre', label: 'Torre de Controle', icon: 'ciclo', exato: true },
  {
    tipo: 'secao',
    label: 'Preparar',
    path: '/torre/estagio/preparar',
    itens: [
      { path: '/oportunidades/salvas', label: 'Oportunidade', icon: 'bookmark' },
      { path: '/ciclo/cotador', label: 'Cotação', icon: 'cotador' },
      { path: '/torre/etapa/cadastro_proposta', label: 'Cadastro de proposta', icon: 'proposta' },
    ],
  },
  {
    tipo: 'secao',
    label: 'Disputar',
    path: '/torre/estagio/disputar',
    itens: [
      { path: '/torre/etapa/disputa', label: 'Disputa', icon: 'disputa' },
      {
        path: '/torre/etapa/aguardando_julgamento',
        label: 'Aguardando julgamento',
        icon: 'calendar',
      },
      { path: '/torre/etapa/julgado_habilitado', label: 'Julgado e habilitado', icon: 'check' },
      {
        path: '/torre/etapa/aguardando_adjudicacao',
        label: 'Aguardando adjudicação',
        icon: 'calendar',
      },
    ],
  },
  {
    tipo: 'secao',
    label: 'Contratar',
    path: '/torre/estagio/contratar',
    itens: [
      // Homologado abre Contratar: ganhou, agora é esperar contrato/empenho.
      { path: '/torre/etapa/homologado', label: 'Homologado', icon: 'check' },
      { path: '/torre/etapa/contrato', label: 'Contrato', icon: 'documentos' },
      { path: '/torre/etapa/empenho', label: 'Empenho / OF', icon: 'empenho' },
    ],
  },
  {
    tipo: 'secao',
    label: 'Receber',
    path: '/torre/estagio/receber',
    itens: [
      { path: '/torre/etapa/entrega', label: 'Entrega', icon: 'produtos' },
      { path: '/torre/etapa/liquidado', label: 'Liquidado', icon: 'spreadsheet' },
      { path: '/torre/etapa/recebido', label: 'Recebido', icon: 'check' },
    ],
  },
  { tipo: 'linha' },
  { tipo: 'item', path: '/ciclo/encerradas', label: 'Encerradas', icon: 'encerradas' },
  // Saíram antes de participar — não são encerradas (ver encerradas.py).
  { tipo: 'item', path: '/ciclo/descartadas', label: 'Descartadas', icon: 'trash', recuo: true },
  // O PDF da proposta comercial (proposta ajustada, enviada depois de ganhar).
  { tipo: 'item', path: '/ciclo/propostas', label: 'Propostas (PDF)', icon: 'proposta' },
  { tipo: 'linha' },
  // Relatórios: só o lugar por enquanto (08/11/2026).
  {
    tipo: 'secao',
    label: 'Relatórios',
    itens: [{ path: '/relatorios', label: 'Em breve', icon: 'spreadsheet' }],
  },
  { tipo: 'linha' },
  // Os cadastros que o Cotador usa: com quem eu disputo, de quem eu compro
  // e o que eu vendo.
  {
    tipo: 'secao',
    label: 'Cadastros',
    itens: [
      { path: '/empresas', label: 'Empresas', icon: 'empresas' },
      { path: '/fornecedores', label: 'Fornecedores', icon: 'fornecedores' },
      { path: '/produtos', label: 'Produtos', icon: 'produtos' },
    ],
  },
];
