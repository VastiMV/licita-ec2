import { Component, OnInit, inject, signal } from '@angular/core';

import { EmPropostaResponse } from '../../../contracts/propostas/proposta.contracts';
import { PropostasService } from '../../../services/propostas/propostas.service';
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
import {
  CotadorModalComponent,
  CotadorModalData,
} from '../../oportunidades/cotador-modal/cotador-modal.component';
import {
  cidadeComUf,
  formatarData,
  formatarMoeda,
  normalizarTitulo,
} from '../../oportunidades/edital-card/edital-card.utils';
import {
  PropostaModalComponent,
  PropostaModalData,
  PropostaModalResultado,
} from './proposta-modal/proposta-modal.component';

/** As chaves das colunas são contrato com `PropostasView.get` em
 * `apps/propostas/views.py`. */
const COLUNAS: readonly ColunaTabela<EmPropostaResponse>[] = [
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
    chave: 'empresa',
    titulo: 'Empresa',
    valor: (linha) => linha.proposta.empresa?.nome ?? 'escolher',
    tom: (linha) => (linha.proposta.empresa ? null : 'alerta'),
    ordenavel: false,
  },
  {
    chave: 'situacao',
    titulo: 'Proposta comercial',
    valor: (linha) => (linha.proposta.documento_gerado ? 'gerada' : 'gerar o Word'),
    secundario: (linha) =>
      linha.proposta.arquivos > 0
        ? `${linha.proposta.arquivos} arquivo${linha.proposta.arquivos > 1 ? 's' : ''}`
        : null,
    tom: (linha) => (linha.proposta.documento_gerado ? 'sucesso' : 'alerta'),
    ordenavel: false,
  },
  {
    chave: 'valor_proposto',
    titulo: 'Proposto',
    valor: (linha) => formatarMoeda(linha.proposta.valor) ?? '—',
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
 * "Ciclo de Licitação / Propostas" — as licitações com proposta gerada no
 * Cotador. Daqui sai tudo o que sobe na plataforma: o Word da proposta, os
 * documentos de habilitação da empresa e os arquivos da licitação.
 */
@Component({
  selector: 'app-propostas-page',
  imports: [DataTableComponent, TabelaAcoesDirective, MenuComponent],
  templateUrl: './propostas.page.html',
  styleUrl: './propostas.page.scss',
})
export class PropostasPage implements OnInit {
  private readonly service = inject(PropostasService);
  private readonly modal = inject(ModalService);

  protected readonly colunas = COLUNAS;

  protected readonly estado = signal<EstadoTabela>(
    estadoInicialTabela({ ordenarPor: 'prazo', direcao: 'asc' }),
  );
  protected readonly linhas = signal<readonly EmPropostaResponse[]>([]);
  protected readonly total = signal(0);
  protected readonly carregando = signal(false);
  protected readonly erro = signal(false);

  protected readonly chaveDe = (linha: EmPropostaResponse) => linha.id;

  ngOnInit(): void {
    this.carregar();
  }

  protected aoMudarEstado(estado: EstadoTabela): void {
    this.estado.set(estado);
    this.carregar();
  }

  protected acoesDe(linha: EmPropostaResponse): readonly ItemMenu[] {
    return [
      { rotulo: 'Abrir proposta', icone: 'proposta', executar: () => this.abrir(linha) },
      { rotulo: 'Ver cotação', icone: 'calculadora', executar: () => this.verCotacao(linha) },
    ];
  }

  protected abrir(linha: EmPropostaResponse): void {
    this.modal
      .abrir<PropostaModalResultado, PropostaModalData>(PropostaModalComponent, {
        propostaId: linha.proposta.id,
      })
      .subscribe((mudou) => {
        if (mudou) this.carregar();
      });
  }

  /** A cotação que gerou a proposta, só para leitura. */
  protected verCotacao(linha: EmPropostaResponse): void {
    this.modal
      .abrir<unknown, CotadorModalData>(CotadorModalComponent, {
        titulo: normalizarTitulo(linha.objeto),
        itens: linha.itens,
        oportunidadeId: linha.id,
        somenteLeitura: true,
      })
      .subscribe();
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
}
