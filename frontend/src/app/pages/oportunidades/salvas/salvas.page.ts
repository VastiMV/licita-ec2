import { Component, OnInit, inject, signal } from '@angular/core';

import { OportunidadeSalvaResponse } from '../../../contracts/licitacoes/oportunidade-salva.contracts';
import { OportunidadesSalvasService } from '../../../services/licitacoes/oportunidades-salvas.service';
import { ModalService } from '../../../shared/overlay/modal.service';
import { DataTableComponent } from '../../../shared/ui/data-table/data-table.component';
import {
  ColunaTabela,
  EstadoTabela,
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
} from '../cotador-modal/cotador-modal.component';
import {
  cidadeComUf,
  formatarData,
  formatarMoeda,
  normalizarTitulo,
} from '../edital-card/edital-card.utils';
import {
  OportunidadeModalComponent,
  OportunidadeModalResultado,
} from './oportunidade-modal/oportunidade-modal.component';

/** As chaves das colunas são contrato com o backend (`ORDENACOES` em
 * `apps/licitacoes/views.py`) — é o que vai no `ordering` do endpoint. */
const COLUNAS: readonly ColunaTabela<OportunidadeSalvaResponse>[] = [
  {
    chave: 'uasg',
    titulo: 'UASG',
    valor: (salva) => salva.uasg || '—',
    secundario: (salva) => salva.orgao_nome || null,
    // Sem `umaLinha`: o nome da unidade embaixo precisa quebrar, senão
    // estica a tabela (igual a Encerradas).
  },
  {
    // O objeto voltou (pedido da operação, 08/11/2026), mas cortado em duas
    // linhas: nunca aumenta a altura da linha — a UASG com o órgão embaixo
    // já ocupa isso. O texto inteiro fica na dica e no card.
    chave: 'objeto',
    titulo: 'Objeto',
    valor: (salva) => normalizarTitulo(salva.objeto) || '—',
    dica: (salva) => salva.objeto || null,
    limiteLinhas: 2,
    ordenavel: false,
  },
  { chave: 'modalidade', titulo: 'Modalidade', valor: (salva) => salva.modalidade || '—' },
  {
    chave: 'cidade',
    titulo: 'Cidade',
    valor: cidadeComUf,
    dica: (salva) => [salva.municipio, salva.uf].filter(Boolean).join(' / ') || null,
    umaLinha: true,
  },
  {
    chave: 'data_publicacao',
    titulo: 'Publicação',
    valor: (salva) => formatarData(salva.data_publicacao) ?? '—',
    umaLinha: true,
  },
  {
    chave: 'prazo',
    titulo: 'Prazo',
    valor: (salva) => formatarData(salva.data_encerramento_proposta) ?? '—',
    umaLinha: true,
  },
  {
    chave: 'valor',
    titulo: 'Estimado',
    valor: (salva) => formatarMoeda(salva.valor_total_estimado) ?? '—',
    numerica: true,
    umaLinha: true,
  },
];

/**
 * "Oportunidades / Salvas" — a lista que a equipe montou a partir da busca.
 *
 * Compartilhada: o que um usuário salva aparece para todos (ver
 * docs/DOMINIO.md). Buscar, ordenar e paginar são sempre consulta nova ao
 * endpoint — a tela nunca tem a lista inteira em memória.
 */
@Component({
  selector: 'app-salvas-page',
  imports: [DataTableComponent, TabelaAcoesDirective, MenuComponent],
  templateUrl: './salvas.page.html',
  styleUrl: './salvas.page.scss',
})
export class SalvasPage implements OnInit {
  private readonly service = inject(OportunidadesSalvasService);
  private readonly modal = inject(ModalService);
  private readonly toast = inject(ToastService);

  protected readonly colunas = COLUNAS;

  protected readonly estado = signal<EstadoTabela>(
    // O prazo que vence primeiro vem primeiro — é por onde o dia começa.
    estadoInicialTabela({ ordenarPor: 'prazo', direcao: 'asc' }),
  );
  protected readonly linhas = signal<readonly OportunidadeSalvaResponse[]>([]);
  protected readonly total = signal(0);
  protected readonly carregando = signal(false);
  protected readonly erro = signal(false);

  protected readonly chaveDe = (salva: OportunidadeSalvaResponse) => salva.id;

  ngOnInit(): void {
    this.carregar();
  }

  protected aoMudarEstado(estado: EstadoTabela): void {
    this.estado.set(estado);
    this.carregar();
  }

  /** As ações de uma linha ficam dentro de um menu, não como botões soltos:
   * é o que mantém a tabela inteira visível num monitor médio, sem rolagem
   * horizontal. */
  protected acoesDe(salva: OportunidadeSalvaResponse): readonly ItemMenu[] {
    return [
      { rotulo: 'Visualizar', icone: 'eye', executar: () => this.visualizar(salva) },
      { rotulo: 'Abrir cotação', icone: 'calculadora', executar: () => this.cotar(salva) },
      { rotulo: 'Excluir', icone: 'trash', tom: 'perigo', executar: () => this.excluir(salva) },
    ];
  }

  protected visualizar(salva: OportunidadeSalvaResponse): void {
    this.modal
      .abrir<OportunidadeModalResultado, OportunidadeSalvaResponse>(
        OportunidadeModalComponent,
        salva,
      )
      .subscribe((resultado) => {
        if (resultado === 'cotar') this.cotar(salva);
      });
  }

  /**
   * Abre o Cotador desta oportunidade — a cotação gravada, se existir, ou
   * uma nova já preenchida com os itens do snapshot do edital.
   *
   * Quem sabe qual dos dois é o caso é o próprio modal: ele pede a cotação
   * pelo id da oportunidade e trata 404 como "ainda não cotada" (ver
   * `CotadorModalComponent`), o que evita uma chamada a mais só pra
   * descobrir isso antes de abrir.
   */
  protected cotar(salva: OportunidadeSalvaResponse): void {
    const dados: CotadorModalData = {
      titulo: normalizarTitulo(salva.objeto),
      itens: salva.itens,
      oportunidadeId: salva.id,
    };

    // Salvou a cotação: a licitação passou para a etapa Cotação e sai daqui.
    this.modal
      .abrir<CotadorModalResultado, CotadorModalData>(CotadorModalComponent, dados)
      .subscribe((resultado) => {
        if (resultado) this.carregar();
      });
  }

  protected excluir(salva: OportunidadeSalvaResponse): void {
    this.modal
      .confirmar({
        titulo: 'Excluir oportunidade salva',
        mensagem:
          `"${this.resumo(salva)}" sai da lista de toda a equipe. ` +
          'Esta ação não poderá ser desfeita. Deseja continuar?',
        confirmarLabel: 'Excluir',
        variantConfirmar: 'danger',
      })
      .subscribe((confirmou) => {
        if (!confirmou) return;

        this.service.remover(salva.id).subscribe({
          next: () => {
            this.toast.sucesso('Oportunidade excluída da lista.');
            this.voltarPaginaSeEsvaziou();
            this.carregar();
          },
          error: () => this.toast.erro('Não foi possível excluir a oportunidade agora.'),
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

  /** Excluir o último item de uma página deixaria a tabela vazia com um
   * paginador dizendo que há mais — volta uma página antes de recarregar. */
  private voltarPaginaSeEsvaziou(): void {
    const estado = this.estado();
    if (this.linhas().length === 1 && estado.pagina > 1) {
      this.estado.set({ ...estado, pagina: estado.pagina - 1 });
    }
  }

  private resumo(salva: OportunidadeSalvaResponse): string {
    const objeto = salva.objeto.trim();
    return objeto.length > 80 ? `${objeto.slice(0, 80)}…` : objeto || 'Oportunidade sem objeto';
  }
}
