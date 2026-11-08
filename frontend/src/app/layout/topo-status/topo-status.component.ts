import { Component, ElementRef, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { catchError, map, of } from 'rxjs';

import { EmpresasService } from '../../services/empresas/empresas.service';
import { IconComponent } from '../../shared/ui/icon/icon.component';

type Painel = 'radar' | 'sentinela' | 'avisos';

/**
 * O topo da tela, como no protótipo "Licita v1.0": de quem é o Licita
 * (empresa e CNPJ), o **Radar** (sugestões), o estado da **Sentinela** e o
 * **sino** de avisos.
 *
 * Radar e Sentinela ainda não existem: cada um mostra o estado verdadeiro
 * ("em breve", "não instalada") e, clicado, explica o que vai aparecer ali.
 * Um "lendo · há 2 min" de mentira faria a operação confiar num vigia que
 * não está vigiando.
 */
@Component({
  selector: 'app-topo-status',
  imports: [IconComponent, RouterLink],
  templateUrl: './topo-status.component.html',
  styleUrl: './topo-status.component.scss',
  host: {
    '(document:click)': 'fecharSeFora($event)',
    '(document:keydown.escape)': 'aberto.set(null)',
  },
})
export class TopoStatusComponent {
  private readonly elemento = inject(ElementRef<HTMLElement>);

  /** A primeira empresa ativa (a Inside é uma só). Sem empresa, nada. */
  protected readonly empresa = toSignal(
    inject(EmpresasService)
      .opcoes()
      .pipe(
        map((empresas) => empresas[0] ?? null),
        catchError(() => of(null)),
      ),
    { initialValue: null },
  );

  protected readonly aberto = signal<Painel | null>(null);

  protected alternar(painel: Painel): void {
    this.aberto.update((atual) => (atual === painel ? null : painel));
  }

  protected fecharSeFora(evento: Event): void {
    if (!this.elemento.nativeElement.contains(evento.target as Node)) this.aberto.set(null);
  }
}
