import { Component, computed, input, output, signal } from '@angular/core';

import { OportunidadeResponse } from '../../../contracts/licitacoes/oportunidade.contracts';
import { IconComponent } from '../../../shared/ui/icon/icon.component';
import { DetalheEstado, EditalCard } from './edital-card.model';
import { PLATAFORMAS } from './plataformas';
import {
  diasRestantes as calcularDiasRestantes,
  estaEncerrada,
  formatarData,
  formatarMoeda,
  normalizarTitulo,
  progressoPercentual,
} from './edital-card.utils';

type Aba = 'itens' | 'documentos';

/** Card de uma oportunidade (= um edital) na busca — layout desktop (6a) e
 * mobile (7a) do handoff em `docs/Mockups/card_oportunidades/README.md`.
 * As duas versões compartilham o mesmo template; a troca é só CSS
 * (`@media` no breakpoint de 880px que o handoff define), não dois DOMs
 * escolhidos em runtime — mais simples de manter e não depende de JS pra
 * saber a largura da tela. */
/** Quantos itens o card mostra recolhido (decisão da operação, GEN-30). */
export const ITENS_RECOLHIDOS = 3;

@Component({
  selector: 'app-edital-card',
  imports: [IconComponent],
  templateUrl: './edital-card.component.html',
  styleUrl: './edital-card.component.scss',
})
export class EditalCardComponent {
  readonly card = input.required<EditalCard>();
  readonly detalhe = input<DetalheEstado | undefined>(undefined);

  /** Já está na lista de salvas — quem sabe disso é a página (ver
   * `PesquisarPage`), o card só desenha. Salvo não volta a "não salvo" por
   * aqui: sair da lista é ação do módulo de salvas (ver docs/DOMINIO.md). */
  readonly salva = input(false);
  readonly salvando = input(false);

  /** Desliga o botão de salvar onde ele não faz sentido — o modal de
   * visualização do módulo de salvas mostra o mesmo card de uma
   * oportunidade que, por definição, já está salva. */
  readonly podeSalvar = input(true);

  /** A página é quem confirma e persiste — o card só avisa que pediram. */
  readonly salvar = output<void>();

  /** A página é quem sabe abrir arquivo (`window.open`) — o card só avisa. */
  readonly baixarEdital = output<void>();

  /** Na busca, só os primeiros itens aparecem, com "Ver todos": licitação
   * com muitos itens obrigava a rolar muito até o próximo card (GEN-30,
   * 11/11/2026). O modal de salvas mostra todos. */
  readonly recolherItens = input(false);

  protected readonly abaAtiva = signal<Aba>('itens');
  protected readonly verTodos = signal(false);
  protected readonly itensRecolhidos = computed(
    () => this.recolherItens() && !this.verTodos() && this.card().itens.length > ITENS_RECOLHIDOS,
  );
  protected readonly itensVisiveis = computed(() =>
    this.itensRecolhidos() ? this.card().itens.slice(0, ITENS_RECOLHIDOS) : this.card().itens,
  );
  protected readonly podeRecolher = computed(
    () => this.recolherItens() && this.card().itens.length > ITENS_RECOLHIDOS,
  );

  // Helpers de formatação expostos pro template (ver edital-card.utils.ts).
  protected readonly moeda = formatarMoeda;
  protected readonly data = formatarData;

  protected readonly contratacao = computed(() => this.card().contratacao);

  protected readonly titulo = computed(() =>
    normalizarTitulo(this.contratacao().contratacao_objeto),
  );

  protected readonly eyebrow = computed(() => {
    const { contratacao_orgao_nome, contratacao_uf, contratacao_uasg } = this.contratacao();
    const orgao = contratacao_orgao_nome ?? '—';
    const uf = contratacao_uf ? ` — ${contratacao_uf}` : '';
    const uasg = contratacao_uasg ? ` · UASG ${contratacao_uasg}` : '';
    return `${orgao}${uf}${uasg}`;
  });

  protected readonly cidade = computed(() => {
    const { contratacao_municipio, contratacao_uf } = this.contratacao();
    if (!contratacao_municipio) return contratacao_uf ?? '—';
    return contratacao_uf ? `${contratacao_municipio} / ${contratacao_uf}` : contratacao_municipio;
  });

  /** Mesmo número do rodapé da tabela de itens (spec: "Valor estimado" do
   * cabeçalho é o total do edital) — `null` se algum item não tiver valor,
   * em vez de somar parcial e fingir que é o total. */
  protected readonly valorTotalEdital = computed(() => {
    const valores = this.card().itens.map((item) => item.valor_total);
    if (valores.length === 0 || valores.some((valor) => valor == null)) return null;
    return (valores as number[]).reduce((soma, valor) => soma + valor, 0);
  });

  protected readonly diasRestantes = computed(() =>
    calcularDiasRestantes(this.contratacao().contratacao_data_encerramento_proposta),
  );

  protected readonly encerrada = computed(() =>
    estaEncerrada(this.contratacao().contratacao_data_encerramento_proposta),
  );

  protected readonly urgente = computed(() => {
    const dias = this.diasRestantes();
    return !this.encerrada() && dias !== null && dias <= 2;
  });

  protected readonly progresso = computed(() =>
    progressoPercentual(
      this.contratacao().contratacao_data_publicacao,
      this.contratacao().contratacao_data_encerramento_proposta,
    ),
  );

  protected readonly rotuloContagem = computed(() => {
    if (this.encerrada()) return 'Encerrada';
    const dias = this.diasRestantes();
    if (dias === null) return null;
    if (dias === 0) return 'Encerra hoje';
    if (dias === 1) return 'Falta 1 dia';
    return `Faltam ${dias} dias`;
  });

  /** `null` esconde o botão de baixar (spec: nada de botão cinza
   * desabilitado quando não há arquivo). */
  protected readonly urlEditalPrincipal = computed(
    () => this.detalhe()?.documentos[0]?.url ?? null,
  );

  /** O botão dourado "Abrir na plataforma" — sempre presente: o backend
   * garante que toda oportunidade é da plataforma escolhida e tem link de
   * disputa (sem link não existe oportunidade, ver docs/DOMINIO.md). O link
   * do detalhe (`linkSistemaOrigem` do PNCP), quando chega, tem prioridade
   * sobre o da busca. */
  protected readonly plataforma = computed(() => {
    const doDetalhe = this.detalhe()?.plataforma ?? null;
    const contratacao = this.contratacao();
    // Quando o detalhe chegou, o `id` dele vale MESMO sendo nulo (nulo =
    // plataforma real, só não registrada) — `??` aqui ressuscitaria o
    // palpite da busca por cima da verdade.
    const id = doDetalhe ? doDetalhe.id : contratacao.plataforma_id;
    const registrada = id ? PLATAFORMAS[id] : undefined;
    return {
      link: doDetalhe?.link ?? contratacao.link_plataforma,
      nome: registrada?.nome ?? doDetalhe?.nome ?? null,
      icone: registrada?.icone ?? null,
    };
  });

  /** Selo CAPAG: o da própria busca chega junto do resultado (caminho da
   * busca textual) e aparece na hora; o do detalhe cobre os caminhos em que
   * a busca não tinha os insumos (navegação/catálogo). */
  protected readonly seloCapag = computed(
    () => this.contratacao().capag ?? this.detalhe()?.capag ?? null,
  );

  protected alternarItens(): void {
    this.verTodos.update((v) => !v);
  }

  protected mudarAba(aba: Aba): void {
    this.abaAtiva.set(aba);
  }

  /** Chips sob a descrição do item — só com dados reais do PNCP; CATSER e
   * "Ampla concorrência" do mockup eram fictícios (README do handoff) e a
   * API não devolve isso hoje, então ficam de fora em vez de inventados. */
  protected chipsDoItem(item: OportunidadeResponse): readonly string[] {
    const chips: string[] = [];
    if (item.criterio_julgamento) chips.push(item.criterio_julgamento);
    if (item.tipo_beneficio) chips.push(item.tipo_beneficio);
    if (item.contratacao_srp) chips.push('Registro de preços');
    return chips;
  }
}
