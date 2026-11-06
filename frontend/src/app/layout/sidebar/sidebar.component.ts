import { Component, computed, inject } from '@angular/core';

import { AuthService } from '../../core/auth/auth.service';
import { IconComponent, type IconName } from '../../shared/ui/icon/icon.component';
import { BrandComponent } from '../brand/brand.component';
import { NavGroupComponent, type NavSubItem } from '../nav-group/nav-group.component';
import { NavItemComponent } from '../nav-item/nav-item.component';
import { SidebarStateService } from './sidebar-state.service';

interface NavLink {
  readonly path: string;
  readonly label: string;
  readonly icon: IconName;
  /** Item de primeiro nível que agrupa outros (ver `NavGroupComponent`) —
   * o pai não é link, quem navega são os filhos. */
  readonly itens?: readonly NavSubItem[];
}

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
  imports: [BrandComponent, NavItemComponent, NavGroupComponent, IconComponent],
  templateUrl: './sidebar.component.html',
  styleUrl: './sidebar.component.scss',
})
export class SidebarComponent {
  protected readonly state = inject(SidebarStateService);
  private readonly auth = inject(AuthService);

  /** Em mobile a Sidebar é um painel off-canvas: navegar fecha o painel.
   * Abrir/fechar um grupo (ver `NavGroupComponent`), não — o clique no
   * cabeçalho do grupo borbulha até aqui, mas não é navegação. */
  protected fecharSeNavegou(evento: Event): void {
    if ((evento.target as HTMLElement).closest('a')) this.state.closeMobile();
  }

  protected readonly links = computed<readonly NavLink[]>(() => [
    ...MENU,
    ...(this.auth.ehSuperusuario() ? [CONFIGURACOES] : []),
  ]);
}

const CONFIGURACOES: NavLink = {
  path: '/configuracoes',
  label: 'Configurações',
  icon: 'configuracoes',
  itens: [
    { path: '/configuracoes/armazenamento', label: 'Armazenamento', icon: 'armazenamento' },
    { path: '/configuracoes/usuarios', label: 'Usuários', icon: 'user' },
  ],
};

const MENU: readonly NavLink[] = [
  // O Ciclo de Licitação: "Visão Geral" é o quadro, e cada etapa embaixo é
  // a lista das licitações que estão nela agora — a licitação sai de uma
  // lista e aparece na seguinte conforme o trabalho anda.
  {
    path: '/ciclo',
    label: 'Ciclo de Licitação',
    icon: 'ciclo',
    itens: [
      { path: '/ciclo/visao-geral', label: 'Visão Geral', icon: 'ciclo' },
      {
        path: '/oportunidades',
        label: 'Oportunidades',
        icon: 'oportunidades',
        itens: [
          { path: '/oportunidades/buscar', label: 'Buscar', icon: 'search' },
          { path: '/oportunidades/salvas', label: 'Salvas', icon: 'bookmark' },
        ],
      },
      { path: '/ciclo/cotador', label: 'Cotador', icon: 'cotador' },
      { path: '/ciclo/propostas', label: 'Propostas', icon: 'proposta' },
      { path: '/ciclo/disputas', label: 'Disputas', icon: 'disputa' },
      { path: '/ciclo/empenhos', label: 'Empenhos', icon: 'empenho' },
      { path: '/ciclo/encerradas', label: 'Encerradas', icon: 'encerradas' },
      // Tiradas da lista antes do prazo — não são encerradas (ver encerradas.py).
      { path: '/ciclo/descartadas', label: 'Descartadas', icon: 'trash' },
    ],
  },
  // Os cadastros que o Cotador usa: com quem eu disputo, de quem eu compro
  // e o que eu vendo.
  {
    path: '/cadastros',
    label: 'Cadastros',
    icon: 'cadastros',
    itens: [
      { path: '/empresas', label: 'Empresas', icon: 'empresas' },
      { path: '/fornecedores', label: 'Fornecedores', icon: 'fornecedores' },
      { path: '/produtos', label: 'Produtos', icon: 'produtos' },
    ],
  },
];
