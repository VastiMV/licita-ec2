import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { CartaoTorre, TorreResponse } from '../../contracts/licitacoes/torre.contracts';
import { TorreService } from '../../services/licitacoes/torre.service';
import { IconComponent } from '../../shared/ui/icon/icon.component';
import { TorreAcoesService } from './torre-acoes.service';
import { TorreCartaoComponent } from './torre-cartao/torre-cartao.component';
import { rotaDaEtapa, rotaDoEstagio } from './torre.utils';

/**
 * A Torre de Controle: os 4 estágios lado a lado (Preparar, Disputar,
 * Contratar, Receber), cada um com as suas etapas em miniatura e os cartões
 * em ordem de urgência. Rola de lado se a tela for estreita — as colunas não
 * se empilham, para a ordem dos estágios nunca se perder.
 *
 * Nada se arrasta: a etapa é calculada no backend, por item, a partir dos
 * fatos (Sentinela, PNCP, Portal da Transparência, lançamentos). Ver
 * `apps/licitacoes/torre.py`.
 */
@Component({
  selector: 'app-torre-page',
  imports: [RouterLink, IconComponent, TorreCartaoComponent],
  templateUrl: './torre.page.html',
  styleUrl: './torre.page.scss',
})
export class TorrePage implements OnInit {
  private readonly servico = inject(TorreService);
  private readonly acoes = inject(TorreAcoesService);

  protected readonly torre = signal<TorreResponse | null>(null);
  protected readonly carregando = signal(true);
  protected readonly erro = signal(false);

  protected readonly emAndamento = computed(
    () => this.torre()?.estagios.reduce((soma, estagio) => soma + estagio.total, 0) ?? 0,
  );

  protected readonly hojePorExtenso = computed(() => {
    const hoje = this.torre()?.hoje;
    if (!hoje) return '';
    const [ano, mes, dia] = hoje.split('-').map(Number);
    return new Date(ano, mes - 1, dia).toLocaleDateString('pt-BR', {
      weekday: 'long',
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    });
  });

  protected readonly rotaDaEtapa = rotaDaEtapa;
  protected readonly rotaDoEstagio = rotaDoEstagio;

  ngOnInit(): void {
    this.carregar();
  }

  protected carregar(): void {
    this.carregando.set(true);
    this.erro.set(false);
    this.servico.torre().subscribe({
      next: (torre) => {
        this.torre.set(torre);
        this.carregando.set(false);
      },
      error: () => {
        this.carregando.set(false);
        this.erro.set(true);
      },
    });
  }

  protected abrir(cartao: CartaoTorre): void {
    this.acoes.abrir(cartao).subscribe((recarregar) => {
      if (recarregar) this.carregar();
    });
  }
}
