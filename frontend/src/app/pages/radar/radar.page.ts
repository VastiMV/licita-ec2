import { Component, OnInit, inject, signal } from '@angular/core';
import { FormControl, ReactiveFormsModule } from '@angular/forms';

import { SugestaoRadarResponse } from '../../contracts/licitacoes/radar.contracts';
import { UFS } from '../../contracts/localidades/uf';
import { RadarService } from '../../services/licitacoes/radar.service';
import { ModalService } from '../../shared/overlay/modal.service';
import { DataTableComponent } from '../../shared/ui/data-table/data-table.component';
import {
  ColunaTabela,
  EstadoTabela,
  estadoInicialTabela,
  parametroOrdenacao,
} from '../../shared/ui/data-table/data-table.model';
import { TabelaAcoesDirective } from '../../shared/ui/data-table/tabela-acoes.directive';
import { IconComponent } from '../../shared/ui/icon/icon.component';
import { SelectComponent } from '../../shared/ui/select/select.component';
import { ToastService } from '../../shared/ui/toast/toast.service';
import {
  cidadeComUf,
  formatarData,
  formatarMoeda,
  normalizarTitulo,
} from '../oportunidades/edital-card/edital-card.utils';
import { RadarModalComponent, RadarModalResultado } from './radar-modal/radar-modal.component';

/** As chaves das colunas são contrato com `ORDENACOES_RADAR` em
 * `apps/licitacoes/views.py`. Mesmas colunas de Salvas (GEN-68: "mantendo
 * a mesma apresentação das oportunidades salvas"), mais o "parecida com". */
const COLUNAS: readonly ColunaTabela<SugestaoRadarResponse>[] = [
  {
    chave: 'uasg',
    titulo: 'UASG',
    valor: (s) => s.uasg || '—',
    secundario: (s) => s.orgao_nome || null,
  },
  {
    chave: 'objeto',
    titulo: 'Objeto',
    valor: (s) => normalizarTitulo(s.objeto) || '—',
    dica: (s) => s.objeto || null,
    limiteLinhas: 2,
    ordenavel: false,
  },
  {
    chave: 'parecido_com',
    titulo: 'Parecida com',
    valor: (s) => s.parecido_com || '—',
    secundario: (s) => (s.por_ganho ? 'a Inside ganhou' : 'salva nos últimos 30 dias'),
    limiteLinhas: 2,
    ordenavel: false,
  },
  {
    chave: 'cidade',
    titulo: 'Cidade',
    valor: cidadeComUf,
    dica: (s) => [s.municipio, s.uf].filter(Boolean).join(' / ') || null,
    umaLinha: true,
  },
  {
    chave: 'data_publicacao',
    titulo: 'Publicação',
    valor: (s) => formatarData(s.data_publicacao) ?? '—',
    umaLinha: true,
  },
  {
    chave: 'prazo',
    titulo: 'Prazo',
    valor: (s) => formatarData(s.data_encerramento_proposta) ?? '—',
    umaLinha: true,
  },
  {
    chave: 'valor',
    titulo: 'Estimado',
    valor: (s) => formatarMoeda(s.valor_total_estimado) ?? '—',
    numerica: true,
    umaLinha: true,
  },
];

/**
 * O Radar (GEN-68, 14/11/2026): compras abertas, em todos os portais,
 * parecidas com o que a equipe salvou nos últimos 30 dias e com o que a
 * Inside ganhou. Achadas às 8h e às 18h; cada uma fica 7 dias ou até a
 * abertura da disputa. Clicar abre o card da busca; "Salvar" leva para
 * Oportunidades.
 */
@Component({
  selector: 'app-radar-page',
  imports: [DataTableComponent, TabelaAcoesDirective, IconComponent, SelectComponent, ReactiveFormsModule],
  templateUrl: './radar.page.html',
  styleUrl: './radar.page.scss',
})
export class RadarPage implements OnInit {
  private readonly service = inject(RadarService);
  private readonly modal = inject(ModalService);
  private readonly toast = inject(ToastService);

  protected readonly colunas = COLUNAS;
  protected readonly ufs = UFS;
  protected readonly uf = new FormControl('', { nonNullable: true });

  /** Sem ordem escolhida, o backend põe as puxadas por item ganho primeiro. */
  protected readonly estado = signal<EstadoTabela>(estadoInicialTabela({}));
  protected readonly linhas = signal<readonly SugestaoRadarResponse[]>([]);
  protected readonly total = signal(0);
  protected readonly carregando = signal(false);
  protected readonly erro = signal(false);

  protected readonly chaveDe = (s: SugestaoRadarResponse) => s.id;

  constructor() {
    this.uf.valueChanges.subscribe(() => {
      this.estado.update((atual) => ({ ...atual, pagina: 1 }));
      this.carregar();
    });
  }

  ngOnInit(): void {
    this.carregar();
  }

  protected aoMudarEstado(estado: EstadoTabela): void {
    this.estado.set(estado);
    this.carregar();
  }

  /** A lixeira da linha (GEN-93, 17/11/2026 — a operação pediu lixeira, não
   * menu; clicar na linha abre o card). Sem confirmação — é limpeza da lista, e a compra
   * continua achável na busca. Fica guardada como exemplo do que ele não
   * quer (a IA do Radar vai usar). */
  protected remover(sugestao: SugestaoRadarResponse): void {
    this.service.remover(sugestao.id).subscribe({
      next: () => {
        this.toast.sucesso('Removida do Radar.');
        if (this.linhas().length === 1 && this.estado().pagina > 1) {
          this.estado.update((atual) => ({ ...atual, pagina: atual.pagina - 1 }));
        }
        this.carregar();
      },
      error: () => this.toast.erro('Não foi possível remover agora.'),
    });
  }

  protected abrir(sugestao: SugestaoRadarResponse): void {
    this.modal
      .abrir<RadarModalResultado, SugestaoRadarResponse>(RadarModalComponent, sugestao)
      .subscribe((resultado) => {
        if (resultado === 'salva') this.carregar();
      });
  }

  private carregar(): void {
    const estado = this.estado();
    this.carregando.set(true);
    this.erro.set(false);
    this.service
      .listar({
        page: estado.pagina,
        page_size: estado.tamanhoPagina,
        ordering: parametroOrdenacao(estado),
        busca: estado.busca,
        uf: this.uf.value,
      })
      .subscribe({
        next: (pagina) => {
          this.linhas.set(pagina.results);
          this.total.set(pagina.count);
          this.carregando.set(false);
        },
        error: () => {
          this.carregando.set(false);
          this.erro.set(true);
          this.linhas.set([]);
          this.total.set(0);
        },
      });
  }
}
