import { DIALOG_DATA, DialogRef } from '@angular/cdk/dialog';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { Observable, map, of } from 'rxjs';

import {
  CotacaoRequest,
  CotacaoResponse,
  ItemCotacaoRequest,
} from '../../../contracts/cotador/cotacao.contracts';
import { FornecedorOpcao } from '../../../contracts/fornecedores/fornecedor.contracts';
import { OportunidadeResponse } from '../../../contracts/licitacoes/oportunidade.contracts';
import { CotadorService } from '../../../services/cotador/cotador.service';
import { PrecoSugerido } from '../../../contracts/produtos/produto.contracts';
import { FornecedoresService } from '../../../services/fornecedores/fornecedores.service';
import { ProdutosService } from '../../../services/produtos/produtos.service';
import {
  ComboboxComponent,
  OpcaoCombo,
  normalizarNome,
} from '../../../shared/ui/combobox/combobox.component';
import { ModalService } from '../../../shared/overlay/modal.service';
import { ModalShellComponent } from '../../../shared/overlay/modal-shell/modal-shell.component';
import { ButtonComponent } from '../../../shared/ui/button/button.component';
import { IconComponent } from '../../../shared/ui/icon/icon.component';
import { parseNumero } from '../../../shared/ui/input-number/input-number.component';
import { ToastService } from '../../../shared/ui/toast/toast.service';
import { FornecedorModalComponent } from '../../fornecedores/fornecedor-modal/fornecedor-modal.component';
import {
  ALVOS_RAPIDOS,
  ItemCalculado,
  ItemCotador,
  OfertaCotador,
  RefProduto,
  PADROES_INICIAIS,
  PadroesCotador,
  calcularItem,
  custoUnitarioDa,
  formatarMoeda,
  formatarPercentual,
  formatarQuantidade,
  melhorOferta,
  ofertaEscolhida,
  referenciaDe,
  tetoDoSlider,
  totalizar,
} from './cotador.model';

/**
 * O que o modal precisa receber: a oportunidade **salva** que está sendo
 * cotada, e os `itens` do snapshot dela para o caso de ainda não haver
 * cotação. Não existe cotar direto da busca — da busca o edital só sai
 * salvo (docs/Tarefas/feat-remover-legado.md, tarefa 6).
 */
export interface CotadorModalData {
  readonly titulo: string;
  readonly itens: readonly OportunidadeResponse[];
  readonly oportunidadeId: number;
  /** Processo encerrado: a cotação é só consulta — sem salvar, e fechar
   * não pergunta nada (o que se mexeu na tela é descartado). */
  readonly somenteLeitura?: boolean;
}

/** O que o modal devolve ao fechar — `undefined` quando nada foi salvo. */
export interface CotadorModalResultado {
  readonly cotacaoId: number;
}

let proximoId = 0;
const novoId = () => `l${++proximoId}`;

/** Quantidade padrão de um item criado à mão (o do edital vem com a dele). */
const QUANTIDADE_PADRAO = 1;

function ref(id: number | null | undefined, nome: string | undefined): RefProduto | null {
  return id ? { id, nome: nome ?? '' } : null;
}

function ofertaVazia(): OfertaCotador {
  return {
    id: novoId(),
    fornecedorId: null,
    nome: '',
    custoProduto: 0,
    frete: 0,
    outros: 0,
  };
}

/**
 * O Cotador — a tela de formação de preço de uma oportunidade salva, aberta
 * como modal a partir da lista de salvas ("Abrir cotação").
 *
 * **Nada é persistido enquanto se mexe.** Os itens vêm preenchidos do
 * edital e a cotação vive na memória desta tela; quem abre, olha e desiste
 * não deixa rastro. É o clique em "Salvar" (ou "Salvar e fechar") que grava.
 *
 * **A conta roda aqui, a gravação confere lá.** `cotador.model.ts` recalcula
 * a cada tecla; o backend refaz a mesma conta ao gravar (`formulas.py`),
 * porque total não pode vir do cliente.
 *
 * O operador não digita o nome do fornecedor: escolhe um do cadastro
 * (módulo Fornecedores) no seletor de cada oferta — e pode cadastrar um
 * novo sem sair daqui.
 *
 * **O que se ajusta aqui é markup, não margem.** Markup é o acréscimo sobre
 * o custo e não tem teto (item barato passa de 100% sem esforço); a margem
 * é o mesmo lucro como % da venda e aparece só como leitura, ao lado de
 * cada controle. Por isso o markup tem campo numérico — o slider sozinho
 * mentiria um limite que não existe (ver `tetoDoSlider`).
 */
@Component({
  selector: 'app-cotador-modal',
  imports: [ModalShellComponent, ButtonComponent, IconComponent, ComboboxComponent],
  templateUrl: './cotador-modal.component.html',
  styleUrl: './cotador-modal.component.scss',
})
export class CotadorModalComponent implements OnInit {
  private readonly dialogRef = inject(DialogRef<CotadorModalResultado>);
  private readonly cotador = inject(CotadorService);
  private readonly fornecedoresService = inject(FornecedoresService);
  private readonly produtos = inject(ProdutosService);
  private readonly modal = inject(ModalService);
  private readonly toast = inject(ToastService);

  protected readonly dados = inject<CotadorModalData>(DIALOG_DATA);

  protected readonly moeda = formatarMoeda;
  protected readonly percentual = formatarPercentual;
  protected readonly quantidade = formatarQuantidade;

  /** Um número dentro de um `<input>`: vírgula decimal, como se digita em
   * pt-BR (mesma escolha do `InputNumberComponent`, que não serve aqui
   * porque esta tela não usa Reactive Forms). */
  protected readonly texto = (valor: number | null) =>
    valor === null ? '' : String(valor).replace('.', ',');

  protected readonly titulo = signal('');
  protected readonly padroes = signal<PadroesCotador>(PADROES_INICIAIS);
  protected readonly itens = signal<readonly ItemCotador[]>([]);

  /** Um item expandido por vez (acordeão): dois painéis abertos deixam a
   * lista impossível de varrer. */
  protected readonly expandido = signal<string | null>(null);
  protected readonly mostrarPadroes = signal(false);
  protected readonly mostrarAjuda = signal(false);

  /** Id da cotação gravada — nulo enquanto ela só existe nesta tela. */
  protected readonly cotacaoId = signal<number | null>(null);
  protected readonly carregando = signal(true);
  protected readonly salvando = signal(false);
  protected readonly exportando = signal(false);

  protected readonly fornecedores = signal<readonly FornecedorOpcao[]>([]);

  /** Um cálculo por item, na ordem da lista. Recalculado a cada mudança de
   * `itens` ou `padroes` — é o que faz a tela responder a cada tecla. */
  protected readonly calculados = computed(() =>
    this.itens().map((item) => calcularItem(item, this.padroes())),
  );
  protected readonly totais = computed(() => totalizar(this.itens(), this.padroes()));

  protected readonly temEconomia = computed(() => this.totais().economia > 0.01);

  /** A carga tributária efetiva da cotação inteira — o imposto embutido
   * como % do valor cotado. Não é o percentual do padrão: itens com tributo
   * próprio puxam a média para cima ou para baixo. */
  protected readonly impostosPercentual = computed(() => {
    const { impostos, valorCotado } = this.totais();
    return valorCotado === 0 ? 0 : (impostos / valorCotado) * 100;
  });

  /**
   * "Para onde vai cada real do valor cotado" (GEN-66, 14/11/2026 — opção A
   * escolhida pela operação): custo + transporte + garantia + impostos +
   * lucro = valor cotado. Alimenta a barra dividida e a tabela ao lado.
   */
  protected readonly fatias = computed(() => {
    const t = this.totais();
    const p = this.padroes();
    const pct = (valor: number) => (t.valorCotado === 0 ? 0 : (valor / t.valorCotado) * 100);
    const freteOutros = t.custo - t.custoProdutos;
    return [
      {
        chave: 'custo',
        rotulo: 'Custo',
        nota: `produtos ${formatarMoeda(t.custoProdutos)} + frete e outros ${formatarMoeda(freteOutros)}`,
        valor: t.custo,
        pct: pct(t.custo),
      },
      {
        chave: 'transporte',
        rotulo: 'Transporte',
        nota: `${formatarPercentual(p.transporte)} do custo`,
        valor: t.transporte,
        pct: pct(t.transporte),
      },
      {
        chave: 'garantia',
        rotulo: 'Garantia',
        nota: `${formatarPercentual(p.garantia)} do custo`,
        valor: t.garantia,
        pct: pct(t.garantia),
      },
      {
        chave: 'impostos',
        rotulo: 'Impostos embutidos',
        nota: '',
        valor: t.impostos,
        pct: pct(t.impostos),
      },
      {
        chave: 'lucro',
        rotulo: 'Lucro total',
        nota: `markup ${formatarPercentual(t.markupMedio)} sobre o custo`,
        valor: t.lucroTotal,
        pct: pct(t.lucroTotal),
      },
    ];
  });

  /** Onde a chave do capital termina e onde fica a reserva, em % da barra. */
  protected readonly larguraCapital = computed(() => {
    const t = this.totais();
    return t.valorCotado === 0 ? 0 : Math.min((t.capital / t.valorCotado) * 100, 100);
  });

  protected readonly posicaoReserva = computed(() => {
    const t = this.totais();
    return t.valorCotado === 0 ? 0 : Math.min((t.precoReserva / t.valorCotado) * 100, 100);
  });

  protected readonly resumoPadroes = computed(() => {
    const p = this.padroes();
    return (
      `Transporte ${formatarPercentual(p.transporte)} · ` +
      `Markup ${formatarPercentual(p.markupMinimo)}–${formatarPercentual(p.markupAlvo)} · ` +
      `Tributos ${formatarPercentual(p.impostos)}`
    );
  });

  ngOnInit(): void {
    this.titulo.set(this.dados.titulo);
    // A cotação vive só na memória do modal até ser salva: clique fora ou
    // Esc não podem jogar o trabalho fora sem perguntar.
    this.dialogRef.disableClose = true;
    this.dialogRef.backdropClick.subscribe(() => this.fechar());
    this.dialogRef.keydownEvents.subscribe((evento) => {
      if (evento.key === 'Escape') this.fechar();
    });
    this.carregarCotacao();
  }

  /** O payload como estava ao abrir (ou ao salvar) — base do "tem alteração
   * não salva?". */
  private readonly estadoSalvo = signal<string | null>(null);

  private marcarSalvo(): void {
    this.estadoSalvo.set(JSON.stringify(this.montarPayload()));
  }

  private temAlteracao(): boolean {
    const salvo = this.estadoSalvo();
    return salvo !== null && salvo !== JSON.stringify(this.montarPayload());
  }

  // ---------- carga ----------

  private carregarCotacao(): void {
    this.cotador.carregarDaOportunidade(this.dados.oportunidadeId).subscribe({
      next: (cotacao) => {
        this.aplicar(cotacao);
        this.marcarSalvo();
        this.carregando.set(false);
        this.carregarFornecedores(true);
      },
      // 404 = oportunidade ainda não cotada. Não é erro: é o sinal de abrir
      // em branco, com os itens do snapshot do edital.
      // Qualquer outro erro NÃO é "não cotada": abrir em branco faria o
      // operador achar que perdeu a cotação — e salvar por cima a apagaria.
      error: (erro: unknown) => {
        if ((erro as { status?: number } | null)?.status !== 404) {
          this.toast.erro('Não foi possível carregar a cotação agora. Tente de novo.');
          this.dialogRef.close();
          return;
        }
        this.montarDoEdital();
        this.marcarSalvo();
        this.carregando.set(false);
        this.carregarFornecedores(false);
      },
    });
  }

  /** Uma cotação nova já nasce com os itens do edital — o operador só
   * amarra o fornecedor e ajusta o que precisar. */
  private montarDoEdital(): void {
    this.itens.set(
      this.dados.itens.map((item, indice) => ({
        id: novoId(),
        numeroItem: item.numero_item ?? String(indice + 1),
        descricao: item.descricao_resumida ?? '',
        unidade: item.unidade_medida ?? '',
        quantidade: item.quantidade ?? QUANTIDADE_PADRAO,
        valorReferencia: item.valor_unitario_estimado,
        markupMinimo: null,
        markupAlvo: null,
        impostos: null,
        ofertas: [ofertaVazia()],
        escolhida: '',
      })),
    );
    // Cada item nasce com uma oferta em branco; `escolhida` aponta pra ela.
    this.itens.update((itens) => itens.map((item) => ({ ...item, escolhida: item.ofertas[0].id })));
    this.expandido.set(this.itens()[0]?.id ?? null);
  }

  private aplicar(cotacao: CotacaoResponse): void {
    this.cotacaoId.set(cotacao.id);
    this.titulo.set(cotacao.titulo || this.dados.titulo);
    this.padroes.set({
      transporte: Number(cotacao.transporte),
      garantia: Number(cotacao.garantia),
      markupMinimo: Number(cotacao.lucro_minimo),
      markupAlvo: Number(cotacao.lucro_maximo),
      impostos: Number(cotacao.impostos),
    });

    this.itens.set(
      cotacao.itens.map((item) => {
        const ofertas = item.ofertas.map((oferta) => ({
          id: novoId(),
          fornecedorId: oferta.fornecedor,
          nome: oferta.nome,
          fabricante: ref(oferta.fabricante, oferta.fabricante_nome),
          marca: ref(oferta.marca, oferta.marca_nome),
          modelo: ref(oferta.modelo, oferta.modelo_nome),
          custoProduto: Number(oferta.custo_produto),
          frete: Number(oferta.frete),
          outros: Number(oferta.outros),
        }));
        const marcada = item.ofertas.findIndex((oferta) => oferta.escolhida);
        return {
          id: novoId(),
          numeroItem: item.numero_item,
          descricao: item.descricao,
          unidade: item.unidade,
          quantidade: Number(item.quantidade),
          valorReferencia: item.valor_referencia === null ? null : Number(item.valor_referencia),
          markupMinimo: item.margem_minima === null ? null : Number(item.margem_minima),
          markupAlvo: item.margem_maxima === null ? null : Number(item.margem_maxima),
          impostos: item.impostos === null ? null : Number(item.impostos),
          ofertas,
          escolhida: ofertas[Math.max(marcada, 0)]?.id ?? '',
        };
      }),
    );
    this.expandido.set(null);
  }

  /** Numa cotação já salva o seletor precisa listar **todos** os
   * fornecedores, inclusive inativos: o que já estava escolhido nela não
   * pode sumir da lista. */
  private carregarFornecedores(todos: boolean): void {
    this.fornecedoresService.opcoes(todos).subscribe({
      next: (opcoes) => this.fornecedores.set(opcoes),
      // Falhar aqui não pode travar a cotação: o operador ainda consegue
      // trabalhar, só não tem o cadastro à mão.
      error: () => this.toast.alerta('Não foi possível carregar o cadastro de fornecedores.'),
    });
  }

  // ---------- leitura para o template ----------

  protected calculoDe(indice: number): ItemCalculado {
    return this.calculados()[indice];
  }

  protected estaExpandido(item: ItemCotador): boolean {
    return this.expandido() === item.id;
  }

  protected indice(posicao: number): string {
    return String(posicao + 1).padStart(2, '0');
  }

  protected nomeDaOferta(oferta: OfertaCotador): string {
    if (oferta.nome) return oferta.nome;
    return this.fornecedores().find((f) => f.id === oferta.fornecedorId)?.nome ?? '';
  }

  protected rotuloDoFornecedor(item: ItemCotador): string {
    const escolhida = ofertaEscolhida(item);
    return escolhida ? this.nomeDaOferta(escolhida) || 'escolher fornecedor' : 'sem fornecedor';
  }

  protected eMelhor(item: ItemCotador, oferta: OfertaCotador): boolean {
    return melhorOferta(item)?.id === oferta.id;
  }

  protected custoDa(oferta: OfertaCotador): number {
    return custoUnitarioDa(oferta);
  }

  /** O unitário estimado do edital — a referência contra a qual se forma o
   * preço. Nulo quando o edital não publicou valor ou o item foi criado à
   * mão. */
  protected readonly estimadoDe = referenciaDe;

  /** O chip que compara o preço proposto com o estimado do edital. Diz o
   * fato ("6,4% acima do estimado") e não a consequência: nem todo edital
   * trata o estimado como preço máximo. Nulo = não há o que comparar. */
  protected comparacaoDe(indice: number): { texto: string; acima: boolean } | null {
    const desvio = this.calculoDe(indice).desvioReferencia;
    if (desvio === null) return null;

    // Abaixo da resolução da tela (uma casa), "0% abaixo" seria ruído.
    if (Math.abs(desvio) < 0.05) return { texto: 'no valor estimado', acima: false };

    return {
      texto: `${formatarPercentual(Math.abs(desvio))} ${desvio > 0 ? 'acima' : 'abaixo'} do estimado`,
      acima: desvio > 0,
    };
  }

  /** O item usa tributo próprio (e não o padrão da cotação). */
  protected temImpostoProprio(item: ItemCotador): boolean {
    return item.impostos !== null;
  }

  // ---------- edição de item ----------

  protected alternar(item: ItemCotador): void {
    this.expandido.update((atual) => (atual === item.id ? null : item.id));
  }

  protected adicionarItem(depoisDe?: string): void {
    const oferta = ofertaVazia();
    const novo: ItemCotador = {
      id: novoId(),
      numeroItem: '',
      descricao: '',
      unidade: '',
      quantidade: QUANTIDADE_PADRAO,
      valorReferencia: null,
      markupMinimo: null,
      markupAlvo: null,
      impostos: null,
      ofertas: [oferta],
      escolhida: oferta.id,
    };

    this.itens.update((itens) => {
      const posicao = depoisDe ? itens.findIndex((i) => i.id === depoisDe) : -1;
      if (posicao < 0) return [...itens, novo];
      return [...itens.slice(0, posicao + 1), novo, ...itens.slice(posicao + 1)];
    });
    this.expandido.set(novo.id);
  }

  protected duplicarItem(item: ItemCotador): void {
    // Os ids das ofertas são refeitos (são locais), e o escolhido é
    // remapeado pela posição — copiar o id apontaria para a oferta do
    // original.
    const posicaoEscolhida = Math.max(
      item.ofertas.findIndex((o) => o.id === item.escolhida),
      0,
    );
    const ofertas = item.ofertas.map((oferta) => ({ ...oferta, id: novoId() }));
    const copia: ItemCotador = {
      ...item,
      id: novoId(),
      ofertas,
      escolhida: ofertas[posicaoEscolhida]?.id ?? '',
    };

    this.itens.update((itens) => {
      const posicao = itens.findIndex((i) => i.id === item.id);
      return [...itens.slice(0, posicao + 1), copia, ...itens.slice(posicao + 1)];
    });
  }

  protected removerItem(item: ItemCotador): void {
    this.itens.update((itens) => itens.filter((i) => i.id !== item.id));
    if (this.expandido() === item.id) this.expandido.set(null);
  }

  protected novoItemNoEnter(evento: KeyboardEvent, depoisDe: string): void {
    if (evento.shiftKey) return;
    evento.preventDefault();
    this.adicionarItem(depoisDe);
  }

  protected alterarDescricao(item: ItemCotador, valor: string): void {
    this.atualizarItem(item.id, (atual) => ({ ...atual, descricao: valor }));
  }

  protected alterarQuantidade(item: ItemCotador, valor: string): void {
    this.atualizarItem(item.id, (atual) => ({
      ...atual,
      quantidade: Math.max(parseNumero(valor) ?? 0, 0),
    }));
  }

  // ---------- fornecedores do item ----------

  protected adicionarOferta(item: ItemCotador): void {
    this.atualizarItem(item.id, (atual) => ({
      ...atual,
      ofertas: [...atual.ofertas, ofertaVazia()],
    }));
  }

  /** Remover é bloqueado quando resta uma só: um item sem nenhuma linha de
   * fornecedor não teria onde receber preço. Se sair a escolhida, a
   * primeira assume. */
  protected removerOferta(item: ItemCotador, oferta: OfertaCotador): void {
    if (item.ofertas.length <= 1) return;
    this.atualizarItem(item.id, (atual) => {
      const ofertas = atual.ofertas.filter((o) => o.id !== oferta.id);
      return {
        ...atual,
        ofertas,
        escolhida: atual.escolhida === oferta.id ? ofertas[0].id : atual.escolhida,
      };
    });
  }

  protected escolherOferta(item: ItemCotador, oferta: OfertaCotador): void {
    this.atualizarItem(item.id, (atual) => ({ ...atual, escolhida: oferta.id }));
  }

  protected vincularFornecedor(item: ItemCotador, oferta: OfertaCotador, valor: string): void {
    const id = valor ? Number(valor) : null;
    const fornecedor = this.fornecedores().find((f) => f.id === id);
    this.atualizarOferta(item.id, oferta.id, (atual) => ({
      ...atual,
      fornecedorId: id,
      // O nome vem do cadastro — é o que a planilha imprime e o que
      // sobrevive se o fornecedor for excluído depois.
      nome: fornecedor?.nome ?? '',
    }));
  }

  // ---------- dropdowns: fornecedor › fabricante › marca › modelo ----------

  protected readonly buscarFornecedor = (termo: string): Observable<readonly OpcaoCombo[]> => {
    const chave = normalizarNome(termo);
    return of(
      this.fornecedores()
        .filter((f) => !chave || normalizarNome(`${f.nome} ${f.fantasia}`).includes(chave))
        .slice(0, 40)
        .map((f) => ({
          id: f.id,
          nome: f.nome,
          detalhe: f.situacao !== 'ativo' ? f.situacao_label : f.fantasia || null,
        })),
    );
  };

  /** Criar fornecedor precisa de CNPJ e e-mail: abre o cadastro completo,
   * já com o nome digitado. */
  protected criarFornecedor(item: ItemCotador, oferta: OfertaCotador) {
    return (): Observable<OpcaoCombo | undefined> => {
      this.cadastrarFornecedor(item, oferta);
      return of(undefined);
    };
  }

  protected fornecedorDe(oferta: OfertaCotador): OpcaoCombo | null {
    return oferta.fornecedorId ? { id: oferta.fornecedorId, nome: oferta.nome } : null;
  }

  protected escolherFornecedor(
    item: ItemCotador,
    oferta: OfertaCotador,
    opcao: OpcaoCombo | null,
  ): void {
    this.vincularFornecedor(item, oferta, opcao ? String(opcao.id) : '');
    this.sugerirPreco(item, { ...oferta, fornecedorId: opcao?.id ?? null });
  }

  protected buscarFabricante(oferta: OfertaCotador) {
    return (termo: string): Observable<readonly OpcaoCombo[]> =>
      this.produtos.opcoesFabricante(termo, oferta.fornecedorId).pipe(
        map((opcoes) =>
          opcoes.map((o) => ({
            id: o.id,
            nome: o.nome,
            destaque: o.afim,
            detalhe: o.afim ? 'vendido por este fornecedor' : null,
          })),
        ),
      );
  }

  /** Criar fabricante já grava a afinidade com o fornecedor da oferta — e
   * se o nome já existe, o backend devolve o existente (não duplica). */
  protected criarFabricante(oferta: OfertaCotador) {
    return (nome: string): Observable<OpcaoCombo | undefined> =>
      this.produtos
        .criarFabricante({
          nome,
          ...(oferta.fornecedorId ? { fornecedor: oferta.fornecedorId } : {}),
        })
        .pipe(map((f) => ({ id: f.id, nome: f.nome })));
  }

  protected escolherFabricante(
    item: ItemCotador,
    oferta: OfertaCotador,
    opcao: OpcaoCombo | null,
  ): void {
    if (opcao?.id === oferta.fabricante?.id) return;
    this.atualizarOferta(item.id, oferta.id, (atual) => ({
      ...atual,
      fabricante: opcao ? { id: opcao.id, nome: opcao.nome } : null,
      marca: null,
      modelo: null,
    }));
  }

  protected buscarMarca(oferta: OfertaCotador) {
    return (termo: string): Observable<readonly OpcaoCombo[]> =>
      oferta.fabricante ? this.produtos.opcoesMarca(oferta.fabricante.id, termo) : of([]);
  }

  protected criarMarca(oferta: OfertaCotador) {
    return (nome: string): Observable<OpcaoCombo | undefined> =>
      oferta.fabricante
        ? this.produtos
            .criarMarca(oferta.fabricante.id, nome)
            .pipe(map((m) => ({ id: m.id, nome: m.nome })))
        : of(undefined);
  }

  protected escolherMarca(
    item: ItemCotador,
    oferta: OfertaCotador,
    opcao: OpcaoCombo | null,
  ): void {
    if (opcao?.id === oferta.marca?.id) return;
    this.atualizarOferta(item.id, oferta.id, (atual) => ({
      ...atual,
      marca: opcao ? { id: opcao.id, nome: opcao.nome } : null,
      modelo: null,
    }));
  }

  protected buscarModelo(oferta: OfertaCotador) {
    return (termo: string): Observable<readonly OpcaoCombo[]> =>
      oferta.marca ? this.produtos.opcoesModelo(oferta.marca.id, termo) : of([]);
  }

  protected criarModelo(oferta: OfertaCotador) {
    return (nome: string): Observable<OpcaoCombo | undefined> =>
      oferta.marca
        ? this.produtos
            .criarModelo(oferta.marca.id, nome)
            .pipe(map((m) => ({ id: m.id, nome: m.nome })))
        : of(undefined);
  }

  protected escolherModelo(
    item: ItemCotador,
    oferta: OfertaCotador,
    opcao: OpcaoCombo | null,
  ): void {
    const modelo = opcao ? { id: opcao.id, nome: opcao.nome } : null;
    this.atualizarOferta(item.id, oferta.id, (atual) => ({ ...atual, modelo }));
    this.sugerirPreco(item, { ...oferta, modelo });
  }

  /** Último custo que este fornecedor deu para este modelo, por oferta. */
  protected readonly sugestoes = signal<Readonly<Record<string, PrecoSugerido>>>({});

  /** Tabela de preços: com fornecedor e modelo escolhidos, busca o último
   * custo. Se o custo do produto ainda está zerado, já preenche; senão só
   * mostra a sugestão ao lado, para o operador decidir. */
  private sugerirPreco(item: ItemCotador, oferta: OfertaCotador): void {
    this.sugestoes.update(({ [oferta.id]: _, ...resto }) => resto);
    if (!oferta.fornecedorId || !oferta.modelo || this.dados.somenteLeitura) return;
    this.produtos.precoSugerido(oferta.fornecedorId, oferta.modelo.id).subscribe((preco) => {
      if (!preco) return;
      this.sugestoes.update((atual) => ({ ...atual, [oferta.id]: preco }));
      if (oferta.custoProduto === 0) this.usarSugestao(item, oferta, preco);
    });
  }

  protected usarSugestao(item: ItemCotador, oferta: OfertaCotador, preco: PrecoSugerido): void {
    this.atualizarOferta(item.id, oferta.id, (atual) => ({
      ...atual,
      custoProduto: Number(preco.custo),
    }));
  }

  protected alterarCusto(
    item: ItemCotador,
    oferta: OfertaCotador,
    campo: 'custoProduto' | 'frete' | 'outros',
    valor: string,
  ): void {
    this.atualizarOferta(item.id, oferta.id, (atual) => ({
      ...atual,
      [campo]: Math.max(parseNumero(valor) ?? 0, 0),
    }));
  }

  /** Cadastrar sem sair da cotação: o fornecedor novo entra na lista e já
   * fica vinculado à oferta que motivou o cadastro. */
  protected cadastrarFornecedor(item: ItemCotador, oferta: OfertaCotador): void {
    this.modal.abrir<FornecedorOpcao, null>(FornecedorModalComponent, null).subscribe((novo) => {
      if (!novo) return;
      this.fornecedores.update((atuais) =>
        [...atuais, novo].sort((a, b) => a.nome.localeCompare(b.nome, 'pt-BR')),
      );
      this.atualizarOferta(item.id, oferta.id, (atual) => ({
        ...atual,
        fornecedorId: novo.id,
        nome: novo.nome,
      }));
      this.toast.sucesso(`"${novo.nome}" entrou no cadastro e foi vinculado ao item.`);
    });
  }

  protected usarMelhor(item: ItemCotador): void {
    const melhor = melhorOferta(item);
    if (melhor) this.escolherOferta(item, melhor);
  }

  /** Aplica o fornecedor mais barato em todos os itens de uma vez — o botão
   * verde do topo da lista. */
  protected aplicarMelhores(): void {
    this.itens.update((itens) =>
      itens.map((item) => {
        const melhor = melhorOferta(item);
        return melhor ? { ...item, escolhida: melhor.id } : item;
      }),
    );
  }

  // ---------- markup e tributos ----------

  /** Os alvos de um clique, e o teto que a régua do slider assume — o
   * markup em si não tem teto (ver `cotador.model.ts`). */
  protected readonly alvosRapidos = ALVOS_RAPIDOS;
  protected readonly teto = tetoDoSlider;

  /** O chip de alvo rápido que está valendo neste item. */
  protected alvoAtivo(indice: number, alvo: number): boolean {
    return Math.abs(this.calculoDe(indice).markupAlvo - alvo) < 0.01;
  }

  protected alterarMarkupMinimo(item: ItemCotador, valor: string): void {
    // Sem teto — só o piso em zero. O campo numérico é a fonte da verdade e
    // aceita o que o slider não alcança.
    const minimo = Math.max(parseNumero(valor) ?? 0, 0);
    this.atualizarItem(item.id, (atual) => {
      const alvo = atual.markupAlvo ?? this.padroes().markupAlvo;
      // Os dois controles se travam entre si: subir o mínimo empurra o alvo.
      return {
        ...atual,
        markupMinimo: minimo,
        markupAlvo: alvo < minimo ? minimo : atual.markupAlvo,
      };
    });
  }

  protected alterarMarkupAlvo(item: ItemCotador, valor: string): void {
    this.aplicarAlvo(item, Math.max(parseNumero(valor) ?? 0, 0));
  }

  /** O alvo de markup do item, vindo do campo, do slider ou de um chip. */
  protected aplicarAlvo(item: ItemCotador, alvo: number): void {
    this.atualizarItem(item.id, (atual) => {
      const minimo = atual.markupMinimo ?? this.padroes().markupMinimo;
      return {
        ...atual,
        markupAlvo: alvo,
        markupMinimo: minimo > alvo ? alvo : atual.markupMinimo,
      };
    });
  }

  /** Liga/desliga o tributo próprio do item. Ao ligar, começa no valor que
   * já estava valendo (o padrão), pra não dar um salto no preço. */
  protected alternarImposto(item: ItemCotador): void {
    this.atualizarItem(item.id, (atual) => ({
      ...atual,
      impostos: atual.impostos === null ? this.padroes().impostos : null,
    }));
  }

  protected alterarImposto(item: ItemCotador, valor: string): void {
    this.atualizarItem(item.id, (atual) => ({
      ...atual,
      impostos: Math.min(Math.max(parseNumero(valor) ?? 0, 0), 100),
    }));
  }

  protected alterarPadrao(campo: keyof PadroesCotador, valor: string): void {
    const numero = Math.max(parseNumero(valor) ?? 0, 0);
    this.padroes.update((atuais) => {
      const proximos = { ...atuais, [campo]: numero };
      // Mesmo travamento dos controles do item, agora no padrão da cotação.
      if (campo === 'markupMinimo' && proximos.markupAlvo < numero) proximos.markupAlvo = numero;
      if (campo === 'markupAlvo' && proximos.markupMinimo > numero) proximos.markupMinimo = numero;
      return proximos;
    });
  }

  // ---------- gravação ----------

  /** Salvou pelo menos uma vez nesta abertura: ao fechar (até pelo X), quem
   * abriu o modal recarrega a lista (GEN-26). */
  private readonly salvouNestaAbertura = signal(false);

  /**
   * Salvar **fica na tela** (GEN-26, 14/11/2026 — decisão da operação): grava e
   * continua editando. "Salvar e fechar" grava e sai.
   */
  protected salvar(fecharDepois = false): void {
    if (this.salvando()) return;
    if (this.itens().length === 0) {
      this.toast.alerta('Uma cotação precisa de pelo menos um item.');
      return;
    }

    this.salvando.set(true);
    this.cotador.salvar(this.montarPayload()).subscribe({
      next: (cotacao) => {
        this.salvando.set(false);
        this.cotacaoId.set(cotacao.id);
        this.salvouNestaAbertura.set(true);
        this.marcarSalvo();
        this.toast.sucesso('Cotação salva.');
        if (fecharDepois) this.dialogRef.close({ cotacaoId: cotacao.id });
      },
      error: () => {
        this.salvando.set(false);
        this.toast.erro('Não foi possível salvar a cotação agora.');
      },
    });
  }

  /**
   * Exportar precisa de uma cotação gravada (a planilha é montada no
   * servidor, a partir dela). Salvar a primeira cotação faz a licitação
   * andar para a etapa de cotação, então o modal pergunta antes em vez de
   * fazer isso escondido.
   */
  protected exportar(): void {
    const id = this.cotacaoId();
    if (id !== null) {
      this.baixar(id);
      return;
    }

    this.modal
      .confirmar({
        titulo: 'Exportar proposta',
        mensagem: 'A planilha é gerada a partir da cotação salva. Deseja salvar a cotação agora?',
        confirmarLabel: 'Salvar e exportar',
      })
      .subscribe((confirmou) => {
        if (!confirmou) return;

        this.salvando.set(true);
        this.cotador.salvar(this.montarPayload()).subscribe({
          next: (cotacao) => {
            this.salvando.set(false);
            this.cotacaoId.set(cotacao.id);
            this.salvouNestaAbertura.set(true);
            this.marcarSalvo();
            this.baixar(cotacao.id);
          },
          error: () => {
            this.salvando.set(false);
            this.toast.erro('Não foi possível salvar a cotação agora.');
          },
        });
      });
  }

  private baixar(id: number): void {
    this.exportando.set(true);
    this.cotador.exportar(id).subscribe({
      next: ({ conteudo, nome }) => {
        this.exportando.set(false);
        // A planilha vem por fetch autenticado (o token vai no header), então
        // o download é montado aqui a partir do blob.
        const url = URL.createObjectURL(conteudo);
        const link = document.createElement('a');
        link.href = url;
        link.download = nome;
        link.click();
        URL.revokeObjectURL(url);
      },
      error: () => {
        this.exportando.set(false);
        this.toast.erro('Não foi possível gerar a planilha agora.');
      },
    });
  }

  protected fechar(): void {
    if (this.dados.somenteLeitura || !this.temAlteracao()) {
      this.dialogRef.close(this.resultado());
      return;
    }
    this.modal
      .confirmar({
        titulo: 'Descartar alterações?',
        mensagem: 'A cotação tem alterações que ainda não foram salvas.',
        confirmarLabel: 'Descartar',
      })
      .subscribe((confirmou) => {
        if (confirmou) this.dialogRef.close(this.resultado());
      });
  }

  /** `undefined` se nada foi salvo nesta abertura. */
  private resultado(): CotadorModalResultado | undefined {
    const id = this.cotacaoId();
    return this.salvouNestaAbertura() && id !== null ? { cotacaoId: id } : undefined;
  }

  private montarPayload(): CotacaoRequest {
    const padroes = this.padroes();
    const itens: ItemCotacaoRequest[] = this.itens().map((item) => ({
      numero_item: item.numeroItem,
      descricao: item.descricao,
      unidade: item.unidade,
      quantidade: item.quantidade,
      valor_referencia: item.valorReferencia,
      // Os nomes do contrato ainda dizem "margem"/"lucro" — o que viaja
      // neles sempre foi o percentual sobre o custo, que é o markup.
      margem_minima: item.markupMinimo,
      margem_maxima: item.markupAlvo,
      impostos: item.impostos,
      ofertas: item.ofertas.map((oferta) => ({
        fornecedor: oferta.fornecedorId,
        nome: this.nomeDaOferta(oferta),
        fabricante: oferta.fabricante?.id ?? null,
        marca: oferta.marca?.id ?? null,
        modelo: oferta.modelo?.id ?? null,
        custo_produto: oferta.custoProduto,
        frete: oferta.frete,
        outros: oferta.outros,
        escolhida: oferta.id === item.escolhida,
      })),
    }));

    return {
      titulo: this.titulo(),
      transporte: padroes.transporte,
      garantia: padroes.garantia,
      lucro_minimo: padroes.markupMinimo,
      lucro_maximo: padroes.markupAlvo,
      impostos: padroes.impostos,
      itens,
      oportunidade_id: this.dados.oportunidadeId,
    };
  }

  // ---------- helpers de estado ----------

  private atualizarItem(id: string, mudar: (item: ItemCotador) => ItemCotador): void {
    this.itens.update((itens) => itens.map((item) => (item.id === id ? mudar(item) : item)));
  }

  private atualizarOferta(
    itemId: string,
    ofertaId: string,
    mudar: (oferta: OfertaCotador) => OfertaCotador,
  ): void {
    this.atualizarItem(itemId, (item) => ({
      ...item,
      ofertas: item.ofertas.map((oferta) => (oferta.id === ofertaId ? mudar(oferta) : oferta)),
    }));
  }
}
