import { NgTemplateOutlet } from '@angular/common';
import { Component, computed, contentChild, effect, input, output } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { debounceTime, distinctUntilChanged } from 'rxjs';

import { IconComponent } from '../icon/icon.component';
import { InputTextComponent } from '../input-text/input-text.component';
import { ColunaTabela, DirecaoOrdenacao, EstadoTabela } from './data-table.model';
import { TabelaAcoesDirective } from './tabela-acoes.directive';

/** Digitar não pode virar uma requisição por tecla — a busca é no endpoint
 * (a tabela mostra só a página atual, filtrar em memória mostraria menos do
 * que existe). */
const ESPERA_BUSCA_MS = 300;

/**
 * Tabela reutilizável do projeto — busca, ordenação por qualquer coluna e
 * paginação, no espírito do DataTables.net mas **integrada ao endpoint**:
 * a tabela nunca tem a lista inteira em memória, então filtrar/ordenar/paginar
 * é sempre uma consulta nova.
 *
 * Ela não guarda estado nem chama serviço: recebe `linhas`/`total`/`estado`
 * prontos e emite o próximo `EstadoTabela` em `estadoMudou`. Quem busca é a
 * página — é o que deixa a mesma tabela servir qualquer domínio.
 *
 * Responsiva sem segundo template: em tela estreita as mesmas células viram
 * uma lista rótulo/valor por linha (`data-rotulo` + CSS), como o card de
 * oportunidade faz. Um DOM só, nada de decidir layout em runtime.
 */
@Component({
  selector: 'app-data-table',
  imports: [ReactiveFormsModule, NgTemplateOutlet, IconComponent, InputTextComponent],
  templateUrl: './data-table.component.html',
  styleUrl: './data-table.component.scss',
})
export class DataTableComponent<T> {
  readonly colunas = input.required<readonly ColunaTabela<T>[]>();
  readonly linhas = input.required<readonly T[]>();
  /** Total de registros no servidor (não o tamanho de `linhas`) — é o que o
   * paginador usa. */
  readonly total = input(0);
  readonly estado = input.required<EstadoTabela>();
  readonly carregando = input(false);
  /** Identidade da linha, para o `track` do `@for`. */
  readonly chaveDe = input.required<(linha: T) => string | number>();
  /** Linhas que precisam saltar aos olhos (ex.: prazo de proposta vencido). */
  readonly destacada = input<(linha: T) => boolean>(() => false);
  readonly rotuloBusca = input('Buscar');
  readonly placeholderBusca = input('Buscar…');
  readonly mensagemVazia = input('Nenhum registro encontrado.');
  readonly tamanhosPagina = input<readonly number[]>([10, 25, 50]);

  readonly estadoMudou = output<EstadoTabela>();
  /** Clique (ou Enter) em qualquer lugar da linha, menos nas Ações — abre o
   * registro (pedido da operação, 08/11/2026). Sem quem escute, nada muda. */
  readonly linhaClicada = output<T>();
  /** Liga o cursor de mão e o foco por teclado nas linhas. */
  readonly linhaClicavel = input(false);

  protected clicarLinha(linha: T, evento: Event): void {
    if (!this.linhaClicavel()) return;
    const alvo = evento.target as HTMLElement | null;
    // Botões, links e o menu de Ações continuam fazendo só o deles.
    if (alvo?.closest('button, a, input, select, textarea, .coluna-acoes')) return;
    this.linhaClicada.emit(linha);
  }

  protected readonly acoes = contentChild(TabelaAcoesDirective);

  protected readonly buscaControl = new FormControl('', { nonNullable: true });

  protected readonly totalPaginas = computed(() =>
    Math.max(1, Math.ceil(this.total() / this.estado().tamanhoPagina)),
  );

  /** "Mostrando 11–20 de 37" — o contador do DataTables, que responde
   * "onde eu estou" sem contar linha na tela. */
  protected readonly primeiroDaPagina = computed(() =>
    this.total() === 0 ? 0 : (this.estado().pagina - 1) * this.estado().tamanhoPagina + 1,
  );
  protected readonly ultimoDaPagina = computed(() =>
    Math.min(this.estado().pagina * this.estado().tamanhoPagina, this.total()),
  );

  protected readonly colunasTotal = computed(() => this.colunas().length + (this.acoes() ? 1 : 0));

  constructor() {
    this.buscaControl.valueChanges
      .pipe(debounceTime(ESPERA_BUSCA_MS), distinctUntilChanged(), takeUntilDestroyed())
      // Volta pra página 1: continuar na página 4 de um resultado que agora
      // tem 1 página só mostraria uma tabela vazia.
      .subscribe((busca) => this.emitir({ busca, pagina: 1 }));

    // A página é dona do estado (pode reiniciar a busca, por exemplo) — o
    // campo acompanha, sem disparar uma requisição por causa disso.
    effect(() => {
      const busca = this.estado().busca;
      if (busca !== this.buscaControl.value) {
        this.buscaControl.setValue(busca, { emitEvent: false });
      }
    });
  }

  protected ordenar(coluna: ColunaTabela<T>): void {
    if (coluna.ordenavel === false) return;

    const estado = this.estado();
    const mesmaColuna = estado.ordenarPor === coluna.chave;
    this.emitir({
      ordenarPor: coluna.chave,
      // Clicar de novo na mesma coluna inverte; coluna nova começa crescente.
      direcao: mesmaColuna && estado.direcao === 'asc' ? 'desc' : 'asc',
      pagina: 1,
    });
  }

  protected direcaoDe(coluna: ColunaTabela<T>): DirecaoOrdenacao | null {
    return this.estado().ordenarPor === coluna.chave ? this.estado().direcao : null;
  }

  /** `aria-sort` do cabeçalho — é assim que um leitor de tela anuncia por
   * qual coluna a tabela está ordenada. */
  protected ariaSort(coluna: ColunaTabela<T>): 'ascending' | 'descending' | 'none' | null {
    if (coluna.ordenavel === false) return null;
    const direcao = this.direcaoDe(coluna);
    if (!direcao) return 'none';
    return direcao === 'asc' ? 'ascending' : 'descending';
  }

  protected irPara(pagina: number): void {
    const destino = Math.min(Math.max(1, pagina), this.totalPaginas());
    if (destino !== this.estado().pagina) this.emitir({ pagina: destino });
  }

  protected mudarTamanho(tamanho: number): void {
    if (tamanho !== this.estado().tamanhoPagina) {
      this.emitir({ tamanhoPagina: tamanho, pagina: 1 });
    }
  }

  protected dicaDe(coluna: ColunaTabela<T>, linha: T): string | null {
    return coluna.dica?.(linha) ?? null;
  }

  protected secundarioDe(coluna: ColunaTabela<T>, linha: T): string | null {
    return coluna.secundario?.(linha) || null;
  }

  protected classeCelula(coluna: ColunaTabela<T>, linha: T): string {
    const tom = coluna.tom?.(linha);
    return tom ? `celula-${tom}` : '';
  }

  private emitir(mudanca: Partial<EstadoTabela>): void {
    this.estadoMudou.emit({ ...this.estado(), ...mudanca });
  }
}
