import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { map } from 'rxjs';

import { CartaoTorre, TorreResponse } from '../../../contracts/licitacoes/torre.contracts';
import { TorreService } from '../../../services/licitacoes/torre.service';
import { TorreAcoesService } from '../torre-acoes.service';
import { TorreCartaoComponent } from '../torre-cartao/torre-cartao.component';
import { rotaDaEtapa, rotaDoEstagio } from '../torre.utils';

/**
 * Um estágio aberto: as etapas dele viram colunas, e os outros três estágios
 * ficam recolhidos em faixas finas, com o total — vê-se o detalhe de um sem
 * perder os outros de vista. Clicar numa faixa abre aquele estágio.
 */
@Component({
  selector: 'app-estagio-page',
  imports: [RouterLink, TorreCartaoComponent],
  templateUrl: './estagio.page.html',
  styleUrl: './estagio.page.scss',
})
export class EstagioPage implements OnInit {
  private readonly servico = inject(TorreService);
  private readonly acoes = inject(TorreAcoesService);

  protected readonly chave = toSignal(
    inject(ActivatedRoute).paramMap.pipe(map((params) => params.get('estagio') ?? '')),
    { initialValue: '' },
  );

  protected readonly torre = signal<TorreResponse | null>(null);
  protected readonly carregando = signal(true);
  protected readonly erro = signal(false);

  protected readonly posicao = computed(
    () => this.torre()?.estagios.findIndex((e) => e.chave === this.chave()) ?? -1,
  );
  protected readonly estagio = computed(() => this.torre()?.estagios[this.posicao()] ?? null);
  protected readonly antes = computed(
    () => this.torre()?.estagios.slice(0, Math.max(this.posicao(), 0)) ?? [],
  );
  protected readonly depois = computed(() =>
    this.posicao() < 0 ? [] : (this.torre()?.estagios.slice(this.posicao() + 1) ?? []),
  );

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

  protected cartoesDa(etapa: string): readonly CartaoTorre[] {
    return this.estagio()?.cartoes.filter((c) => c.etapa === etapa) ?? [];
  }

  protected abrir(cartao: CartaoTorre): void {
    this.acoes.abrir(cartao).subscribe((recarregar) => {
      if (recarregar) this.carregar();
    });
  }
}
