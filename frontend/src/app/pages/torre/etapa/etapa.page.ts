import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { map } from 'rxjs';

import { CartaoTorre, TorreResponse } from '../../../contracts/licitacoes/torre.contracts';
import { TorreService } from '../../../services/licitacoes/torre.service';
import { formatarData, normalizarTitulo } from '../../oportunidades/edital-card/edital-card.utils';
import { TorreAcoesService } from '../torre-acoes.service';
import { localDoCartao, moeda, orgaoDoCartao, resumoDoItem, rotaDoEstagio } from '../torre.utils';

/**
 * A lista de uma etapa, como as listas de hoje do Licita: uma linha por
 * licitação, na ordem de urgência da Torre. É o que o menu abre ao clicar
 * numa etapa. Oportunidade e Cotação têm lista própria (Salvas e Cotador).
 */
@Component({
  selector: 'app-etapa-page',
  imports: [RouterLink],
  templateUrl: './etapa.page.html',
  styleUrl: './etapa.page.scss',
})
export class EtapaPage implements OnInit {
  private readonly servico = inject(TorreService);
  private readonly acoes = inject(TorreAcoesService);

  protected readonly chave = toSignal(
    inject(ActivatedRoute).paramMap.pipe(map((params) => params.get('etapa') ?? '')),
    { initialValue: '' },
  );

  protected readonly torre = signal<TorreResponse | null>(null);
  protected readonly carregando = signal(true);
  protected readonly erro = signal(false);

  protected readonly estagio = computed(
    () =>
      this.torre()?.estagios.find((e) => e.etapas.some((x) => x.chave === this.chave())) ?? null,
  );
  protected readonly rotulo = computed(
    () => this.estagio()?.etapas.find((x) => x.chave === this.chave())?.rotulo ?? '',
  );
  protected readonly cartoes = computed(
    () => this.estagio()?.cartoes.filter((c) => c.etapa === this.chave()) ?? [],
  );

  protected readonly local = localDoCartao;
  protected readonly orgao = orgaoDoCartao;
  protected readonly titulo = normalizarTitulo;
  protected readonly resumoDoItem = resumoDoItem;
  protected readonly moeda = moeda;
  protected readonly data = formatarData;
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

  protected abrirLinha(cartao: CartaoTorre, evento: Event): void {
    if ((evento.target as HTMLElement | null)?.closest('button, a')) return;
    this.abrir(cartao);
  }

  protected abrir(cartao: CartaoTorre): void {
    this.acoes.abrir(cartao).subscribe((recarregar) => {
      if (recarregar) this.carregar();
    });
  }
}
