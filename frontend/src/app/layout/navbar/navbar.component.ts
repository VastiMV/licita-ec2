import { Component, inject } from '@angular/core';

import { IconComponent } from '../../shared/ui/icon/icon.component';
import { BrandComponent } from '../brand/brand.component';
import { ProfileMenuComponent } from '../profile-menu/profile-menu.component';
import { SidebarStateService } from '../sidebar/sidebar-state.service';
import { TopoStatusComponent } from '../topo-status/topo-status.component';

/**
 * Topbar das páginas de módulo — em mobile mostra o hamburguer (abre a
 * `Sidebar` off-canvas) e a marca compacta; em desktop some quase todo
 * (marca e navegação já vivem na `Sidebar`) e sobra só o menu de conta.
 * Não é usada no login: essa página é independente, mostra só a `Brand`
 * (ver `pages/auth/login`).
 */
@Component({
  selector: 'app-navbar',
  imports: [BrandComponent, IconComponent, ProfileMenuComponent, TopoStatusComponent],
  templateUrl: './navbar.component.html',
  styleUrl: './navbar.component.scss',
})
export class NavbarComponent {
  protected readonly sidebarState = inject(SidebarStateService);
}
