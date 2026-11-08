import { Component, computed, input, signal } from '@angular/core';

import { IconComponent, IconName } from '../../shared/ui/icon/icon.component';
import { NavItemComponent } from '../nav-item/nav-item.component';

/** Um item de submenu — mesma forma de um `NavItemComponent`. Com `itens`,
 * é um subgrupo ("Ciclo de Licitação" → "Oportunidades" → "Buscar"). */
export interface NavSubItem {
  readonly path: string;
  readonly label: string;
  readonly icon: IconName;
  readonly itens?: readonly NavSubItem[];
  /** Acende só no endereço exato (ver `NavItemComponent.exato`). */
  readonly exato?: boolean;
}

/** Um item do trilho de ícones — os grupos achatados. */
interface ItemPlano {
  readonly path: string;
  readonly label: string;
  readonly icon: IconName;
  readonly exato?: boolean;
}

function achatar(itens: readonly NavSubItem[]): ItemPlano[] {
  return itens.flatMap((item) => (item.itens ? achatar(item.itens) : [item]));
}

/**
 * Item de menu que agrupa outros ("Oportunidades" → "Buscar" / "Salvas").
 * O pai não é link: ele abre e fecha o grupo — quem navega são os filhos.
 * Grupos se aninham: um filho com `itens` vira um subgrupo ("Ciclo de
 * Licitação" → "Oportunidades" → "Buscar").
 *
 * Com a Sidebar recolhida (trilho de ícones) o grupo desaparece e os filhos
 * viram itens soltos, cada um com o próprio ícone e tooltip: esconder um
 * módulo inteiro atrás de um menu que não dá pra abrir seria pior que perder
 * o agrupamento.
 */
@Component({
  selector: 'app-nav-group',
  imports: [IconComponent, NavItemComponent],
  templateUrl: './nav-group.component.html',
  styleUrl: './nav-group.component.scss',
})
export class NavGroupComponent {
  readonly label = input.required<string>();
  readonly icon = input.required<IconName>();
  readonly itens = input.required<readonly NavSubItem[]>();

  /** Modo ícone-só (Sidebar recolhida em desktop). */
  readonly compact = input(false);

  /** Começa aberto: são poucos itens e o grupo é o caminho para a tela
   * inicial do app — abrir na mão a cada visita seria atrito puro. */
  protected readonly aberto = signal(true);

  /** Trilho de ícones: o grupo some e ficam só os itens que navegam. */
  protected readonly planos = computed(() => achatar(this.itens()));

  protected alternar(): void {
    this.aberto.update((valor) => !valor);
  }
}
