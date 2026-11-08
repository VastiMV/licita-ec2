import { Component, OnInit, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';

import {
  DescartadaResponse,
  EtapaDescarte,
  MOTIVOS_DESCARTE,
} from '../../../contracts/licitacoes/descartada.contracts';
import { UFS } from '../../../contracts/localidades/uf';
import { EncerradasService } from '../../../services/licitacoes/encerradas.service';
import { ModalService } from '../../../shared/overlay/modal.service';
import { ButtonComponent } from '../../../shared/ui/button/button.component';
import { DataTableComponent } from '../../../shared/ui/data-table/data-table.component';
import {
  ColunaTabela,
  EstadoTabela,
  estadoInicialTabela,
  parametroOrdenacao,
} from '../../../shared/ui/data-table/data-table.model';
import { TabelaAcoesDirective } from '../../../shared/ui/data-table/tabela-acoes.directive';
import { DatePickerComponent } from '../../../shared/ui/date-picker/date-picker.component';
import { hojeIso, somarDias } from '../../../shared/ui/date-picker/date-picker.utils';
import { InputTextComponent } from '../../../shared/ui/input-text/input-text.component';
import { ItemMenu, MenuComponent } from '../../../shared/ui/menu/menu.component';
import { SelectComponent } from '../../../shared/ui/select/select.component';
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
import {
  ProcessoModalComponent,
  ProcessoModalResultado,
} from '../encerradas/processo-modal/processo-modal.component';

/** Período que a tela abre consultando — o usuário muda antes de pesquisar. */
const JANELA_PADRAO_DIAS = 90;

/** Valores especiais do campo Período (os outros são meses `aaaa-mm`). */
const PADRAO = 'ultimos';
const PERSONALIZADO = 'datas';

export const ROTULO_ETAPA: Record<EtapaDescarte, string> = {
  oportunidade: 'Oportunidade',
  cotacao: 'Cotação',
};

const NOMES_MES = [
  'janeiro',
  'fevereiro',
  'março',
  'abril',
  'maio',
  'junho',
  'julho',
  'agosto',
  'setembro',
  'outubro',
  'novembro',
  'dezembro',
];

/** Os últimos 12 meses, do atual para trás — `value` é `aaaa-mm`. */
export function ultimosMeses(hoje: string, quantos = 12): { value: string; label: string }[] {
  let [ano, mes] = hoje.split('-').map(Number);
  const meses: { value: string; label: string }[] = [];
  for (let i = 0; i < quantos; i++) {
    meses.push({
      value: `${ano}-${String(mes).padStart(2, '0')}`,
      label: `${NOMES_MES[mes - 1]} de ${ano}`,
    });
    mes -= 1;
    if (mes === 0) {
      mes = 12;
      ano -= 1;
    }
  }
  return meses;
}

/** Primeiro e último dia do mês `aaaa-mm`, em `aaaa-mm-dd`. */
export function limitesDoMes(mes: string): { inicio: string; fim: string } {
  const [ano, m] = mes.split('-').map(Number);
  const ultimoDia = new Date(Date.UTC(ano, m, 0)).getUTCDate();
  const mm = String(m).padStart(2, '0');
  return { inicio: `${ano}-${mm}-01`, fim: `${ano}-${mm}-${String(ultimoDia).padStart(2, '0')}` };
}

/** As chaves das colunas são contrato com `ORDENACOES_DESCARTADAS` em
 * `apps/licitacoes/views.py`. */
const COLUNAS: readonly ColunaTabela<DescartadaResponse>[] = [
  {
    chave: 'uasg',
    titulo: 'UASG',
    valor: (linha) => linha.uasg || '—',
    secundario: (linha) => linha.orgao_nome || null,
    dica: (linha) => linha.objeto || null,
  },
  {
    chave: 'cidade',
    titulo: 'Cidade',
    valor: cidadeComUf,
    dica: (linha) => [linha.municipio, linha.uf].filter(Boolean).join(' / ') || null,
    umaLinha: true,
  },
  {
    chave: 'descartada_em',
    titulo: 'Descartada',
    valor: (linha) => formatarData(linha.descartada_em) ?? '—',
    secundario: (linha) => (linha.removida_por ? `por ${linha.removida_por}` : null),
    umaLinha: true,
  },
  {
    chave: 'motivo',
    titulo: 'Motivo',
    valor: (linha) => linha.motivo_label,
    // Quem, quando, em que etapa e com que preço — "ele vai esquecer".
    secundario: (linha) => linha.motivo_detalhe || null,
  },
  {
    chave: 'estava_em',
    titulo: 'Estava em',
    valor: (linha) => ROTULO_ETAPA[linha.estava_em],
    ordenavel: false,
  },
  {
    chave: 'valor_cotado',
    titulo: 'Cotado',
    valor: (linha) => formatarMoeda(linha.valor_cotado) ?? '—',
    numerica: true,
    umaLinha: true,
    ordenavel: false,
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
 * "Ciclo de Licitação / Descartadas" — tudo que saiu do ciclo antes de
 * participar do certame: tirada da lista antes do prazo, ou o prazo
 * venceu, com ou sem cotação. Encerradas é só quem participou (ver
 * `encerradas.py`).
 * Nada é apagado: o processo e a cotação continuam consultáveis.
 */
@Component({
  selector: 'app-descartadas-page',
  imports: [
    ReactiveFormsModule,
    DataTableComponent,
    TabelaAcoesDirective,
    MenuComponent,
    DatePickerComponent,
    SelectComponent,
    InputTextComponent,
    ButtonComponent,
  ],
  templateUrl: './descartadas.page.html',
  styleUrl: './descartadas.page.scss',
})
export class DescartadasPage implements OnInit {
  private readonly service = inject(EncerradasService);
  private readonly modal = inject(ModalService);
  private readonly fb = inject(FormBuilder);

  protected readonly colunas = COLUNAS;
  protected readonly motivos = MOTIVOS_DESCARTE;
  /** Um campo só para o período — mantém os filtros numa linha. "Escolher
   * datas…" é o único que mostra o "de"/"até". */
  protected readonly periodos = [
    { value: PADRAO, label: `Últimos ${JANELA_PADRAO_DIAS} dias` },
    ...ultimosMeses(hojeIso()),
    { value: PERSONALIZADO, label: 'Escolher datas…' },
  ];
  protected readonly escolhendoDatas = signal(false);
  protected readonly ufs = UFS;

  protected readonly filtros = this.fb.nonNullable.group({
    /** Escolha da tela que preenche "de" e "até". Não vai para a API. */
    periodo: PADRAO,
    data_inicial: somarDias(hojeIso(), -JANELA_PADRAO_DIAS),
    data_final: hojeIso(),
    motivo: '',
    uasg: '',
    uf: '',
  });

  constructor() {
    this.filtros.controls.periodo.valueChanges.pipe(takeUntilDestroyed()).subscribe((periodo) => {
      this.escolhendoDatas.set(periodo === PERSONALIZADO);
      if (periodo === PADRAO) {
        this.filtros.patchValue({
          data_inicial: somarDias(hojeIso(), -JANELA_PADRAO_DIAS),
          data_final: hojeIso(),
        });
      } else if (periodo !== PERSONALIZADO) {
        const { inicio, fim } = limitesDoMes(periodo);
        this.filtros.patchValue({ data_inicial: inicio, data_final: fim });
      }
    });
  }

  protected readonly estado = signal<EstadoTabela>(
    estadoInicialTabela({ ordenarPor: 'descartada_em', direcao: 'desc' }),
  );
  protected readonly linhas = signal<readonly DescartadaResponse[]>([]);
  protected readonly total = signal(0);
  protected readonly carregando = signal(false);
  protected readonly erro = signal(false);

  protected readonly chaveDe = (linha: DescartadaResponse) => linha.id;

  ngOnInit(): void {
    this.carregar();
  }

  protected pesquisar(): void {
    this.estado.update((atual) => ({ ...atual, pagina: 1 }));
    this.carregar();
  }

  protected aoMudarEstado(estado: EstadoTabela): void {
    this.estado.set(estado);
    this.carregar();
  }

  protected acoesDe(linha: DescartadaResponse): readonly ItemMenu[] {
    const itens: ItemMenu[] = [
      { rotulo: 'Ver processo', icone: 'eye', executar: () => this.verProcesso(linha) },
    ];
    if (linha.cotacao_id !== null) {
      itens.push({
        rotulo: 'Ver cotação',
        icone: 'calculadora',
        executar: () => this.verCotacao(linha),
      });
    }
    return itens;
  }

  protected verProcesso(linha: DescartadaResponse): void {
    this.modal
      .abrir<ProcessoModalResultado, DescartadaResponse>(ProcessoModalComponent, linha)
      .subscribe((resultado) => {
        if (resultado === 'cotacao') this.verCotacao(linha);
      });
  }

  protected verCotacao(linha: DescartadaResponse): void {
    this.modal
      .abrir<CotadorModalResultado, CotadorModalData>(CotadorModalComponent, {
        titulo: normalizarTitulo(linha.objeto),
        itens: linha.itens,
        oportunidadeId: linha.id,
        somenteLeitura: true,
      })
      .subscribe();
  }

  private carregar(): void {
    const estado = this.estado();
    const { periodo: _periodo, ...filtros } = this.filtros.getRawValue();
    this.carregando.set(true);
    this.erro.set(false);

    this.service
      .descartadas({
        page: estado.pagina,
        page_size: estado.tamanhoPagina,
        ordering: parametroOrdenacao(estado),
        busca: estado.busca,
        ...filtros,
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
