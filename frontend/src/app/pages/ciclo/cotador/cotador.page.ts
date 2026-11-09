import { Component, OnInit, inject, signal } from '@angular/core';

import { EmCotacaoResponse, SeloCotacao } from '../../../contracts/licitacoes/em-cotacao.contracts';
import { CotadorService } from '../../../services/cotador/cotador.service';
import { EmCotacaoService } from '../../../services/licitacoes/em-cotacao.service';
import { PropostasService } from '../../../services/propostas/propostas.service';
import { ModalService } from '../../../shared/overlay/modal.service';
import { DataTableComponent } from '../../../shared/ui/data-table/data-table.component';
import {
  ColunaTabela,
  EstadoTabela,
  TomCelula,
  estadoInicialTabela,
  parametroOrdenacao,
} from '../../../shared/ui/data-table/data-table.model';
import { TabelaAcoesDirective } from '../../../shared/ui/data-table/tabela-acoes.directive';
import { ItemMenu, MenuComponent } from '../../../shared/ui/menu/menu.component';
import { ToastService } from '../../../shared/ui/toast/toast.service';
import {
  CotadorModalComponent,
  CotadorModalData,
  CotadorModalResultado,
} from '../../oportunidades/cotador-modal/cotador-modal.component';
import {
  cidadeComUf,
  formatarData,
  formatarMoeda,
  normalizarTitulo,
} from '../../oportunidades/edital-card/edital-card.utils';

const TOM_DO_SELO: Record<SeloCotacao['nivel'], TomCelula | null> = {
  ok: 'sucesso',
  neutro: null,
  aviso: 'alerta',
  alerta: 'perigo',
};

/** As chaves das colunas são contrato com `ORDENACOES_COTADOR` em
 * `apps/licitacoes/views.py`. */
const COLUNAS: readonly ColunaTabela<EmCotacaoResponse>[] = [
  {
    chave: 'uasg',
    titulo: 'UASG',
    valor: (linha) => linha.uasg || '—',
    secundario: (linha) => linha.orgao_nome || null,
  },
  {
    // Como em Salvas (08/11/2026): o objeto em até duas linhas, sem aumentar
    // a altura da linha; o texto inteiro fica na dica.
    chave: 'objeto',
    titulo: 'Objeto',
    valor: (linha) => normalizarTitulo(linha.objeto) || '—',
    dica: (linha) => linha.objeto || null,
    limiteLinhas: 2,
    ordenavel: false,
  },
  {
    chave: 'cidade',
    titulo: 'Cidade',
    valor: cidadeComUf,
    dica: (linha) => [linha.municipio, linha.uf].filter(Boolean).join(' / ') || null,
    umaLinha: true,
  },
  {
    chave: 'prazo',
    titulo: 'Prazo',
    valor: (linha) => formatarData(linha.data_encerramento_proposta) ?? '—',
    umaLinha: true,
  },
  {
    chave: 'situacao',
    titulo: 'Situação',
    valor: (linha) => linha.selo.texto,
    secundario: (linha) => linha.selo.faltas[0] ?? null,
    dica: (linha) => linha.selo.faltas.join(' · ') || null,
    tom: (linha) => TOM_DO_SELO[linha.selo.nivel],
    ordenavel: false,
  },
  {
    chave: 'atualizada_em',
    titulo: 'Atualizada',
    valor: (linha) => formatarData(linha.cotacao_atualizada_em) ?? '—',
    umaLinha: true,
  },
  {
    chave: 'valor_cotado',
    titulo: 'Cotado',
    valor: (linha) => formatarMoeda(linha.valor_cotado) ?? '—',
    numerica: true,
    umaLinha: true,
  },
  {
    chave: 'valor',
    titulo: 'Estimado',
    valor: (linha) => formatarMoeda(linha.valor_total_estimado) ?? '—',
    numerica: true,
    umaLinha: true,
  },
];

/**
 * "Ciclo de Licitação / Cotador" — as salvas que já têm cotação e ainda não
 * viraram proposta. A etapa é calculada no backend: salvar a cotação de uma
 * salva a traz para cá; prazo vencido a leva para Encerradas.
 */
@Component({
  selector: 'app-cotador-page',
  imports: [DataTableComponent, TabelaAcoesDirective, MenuComponent],
  templateUrl: './cotador.page.html',
  styleUrl: './cotador.page.scss',
})
export class CotadorPage implements OnInit {
  private readonly service = inject(EmCotacaoService);
  private readonly cotador = inject(CotadorService);
  private readonly propostas = inject(PropostasService);
  private readonly modal = inject(ModalService);
  private readonly toast = inject(ToastService);

  protected readonly colunas = COLUNAS;

  protected readonly estado = signal<EstadoTabela>(
    // O prazo que vence primeiro vem primeiro — é por onde o dia começa.
    estadoInicialTabela({ ordenarPor: 'prazo', direcao: 'asc' }),
  );
  protected readonly linhas = signal<readonly EmCotacaoResponse[]>([]);
  protected readonly total = signal(0);
  protected readonly carregando = signal(false);
  protected readonly erro = signal(false);

  protected readonly chaveDe = (linha: EmCotacaoResponse) => linha.id;

  ngOnInit(): void {
    this.carregar();
  }

  protected aoMudarEstado(estado: EstadoTabela): void {
    this.estado.set(estado);
    this.carregar();
  }

  protected acoesDe(linha: EmCotacaoResponse): readonly ItemMenu[] {
    return [
      { rotulo: 'Abrir cotação', icone: 'calculadora', executar: () => this.abrirCotacao(linha) },
      { rotulo: 'Gerar proposta', icone: 'proposta', executar: () => this.gerarProposta(linha) },
      {
        rotulo: 'Excluir cotação',
        icone: 'trash',
        tom: 'perigo',
        executar: () => this.excluir(linha),
      },
    ];
  }

  protected abrirCotacao(linha: EmCotacaoResponse): void {
    this.modal
      .abrir<CotadorModalResultado, CotadorModalData>(CotadorModalComponent, {
        titulo: normalizarTitulo(linha.objeto),
        itens: linha.itens,
        oportunidadeId: linha.id,
      })
      .subscribe((resultado) => {
        if (resultado) this.carregar();
      });
  }

  /** Gerar a proposta leva a licitação para a etapa Proposta: sai daqui e
   * aparece na coluna Proposta do quadro. O sistema avisa o que falta na
   * cotação, mas não trava. */
  protected gerarProposta(linha: EmCotacaoResponse): void {
    const aviso =
      linha.selo.nivel === 'ok' ? '' : ` Atenção: ${linha.selo.faltas[0] ?? linha.selo.texto}.`;
    this.modal
      .confirmar({
        titulo: 'Gerar proposta',
        mensagem:
          `A proposta de "${this.resumo(linha)}" será gerada com o valor cotado de ` +
          `${formatarMoeda(linha.valor_cotado)}, e a licitação passa para a etapa Proposta.` +
          aviso,
        confirmarLabel: 'Gerar proposta',
      })
      .subscribe((confirmou) => {
        if (!confirmou) return;

        this.propostas.gerar(linha.id).subscribe({
          next: () => {
            this.toast.sucesso('Proposta gerada — a licitação passou para Proposta.');
            this.voltarPaginaSeEsvaziou();
            this.carregar();
          },
          error: () => this.toast.erro('Não foi possível gerar a proposta agora.'),
        });
      });
  }

  /** Como no quadro: excluir apaga a cotação e a licitação volta para
   * Oportunidade (Salvas) — a oportunidade salva continua. */
  protected excluir(linha: EmCotacaoResponse): void {
    this.modal
      .confirmar({
        titulo: 'Excluir cotação',
        mensagem:
          `A cotação de "${this.resumo(linha)}" será apagada e a licitação volta para ` +
          'Oportunidade. A oportunidade salva continua. Deseja continuar?',
        confirmarLabel: 'Excluir cotação',
        variantConfirmar: 'danger',
      })
      .subscribe((confirmou) => {
        if (!confirmou) return;

        this.cotador.remover(linha.cotacao_id).subscribe({
          next: () => {
            this.toast.sucesso('Cotação excluída — voltou para Oportunidade.');
            this.voltarPaginaSeEsvaziou();
            this.carregar();
          },
          error: (erro: { status?: number }) =>
            this.toast.erro(
              erro?.status === 409
                ? 'A proposta já foi gerada a partir desta cotação.'
                : 'Não foi possível excluir a cotação agora.',
            ),
        });
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

  private voltarPaginaSeEsvaziou(): void {
    const estado = this.estado();
    if (this.linhas().length === 1 && estado.pagina > 1) {
      this.estado.set({ ...estado, pagina: estado.pagina - 1 });
    }
  }

  private resumo(linha: EmCotacaoResponse): string {
    const objeto = linha.objeto.trim();
    return objeto.length > 80 ? `${objeto.slice(0, 80)}…` : objeto || 'Licitação sem objeto';
  }
}
