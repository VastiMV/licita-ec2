import { Component, computed, input, output } from '@angular/core';

import { CartaoTorre } from '../../../contracts/licitacoes/torre.contracts';
import { IconComponent } from '../../../shared/ui/icon/icon.component';
import { formatarData, normalizarTitulo } from '../../oportunidades/edital-card/edital-card.utils';
import { localDoCartao, moeda, nivelDoCartao, orgaoDoCartao, resumoDoItem } from '../torre.utils';

/** Quantos itens o cartão lista; o resto vira "+N". */
const MAX_ITENS = 3;

/**
 * Um cartão da Torre: a etapa em que a licitação está (pílula colorida pelo
 * estágio), de quem é, o que a empresa disputa nela, quanto vale e as
 * etiquetas que pedem atenção. Clicar emite `abrir` — quem decide o que
 * abrir é `TorreAcoesService`.
 */
@Component({
  selector: 'app-torre-cartao',
  imports: [IconComponent],
  templateUrl: './torre-cartao.component.html',
  styleUrl: './torre-cartao.component.scss',
})
export class TorreCartaoComponent {
  readonly cartao = input.required<CartaoTorre>();
  readonly abrir = output<CartaoTorre>();

  protected readonly nivel = computed(() => nivelDoCartao(this.cartao()));
  protected readonly local = computed(() => localDoCartao(this.cartao()));
  protected readonly orgao = computed(() => orgaoDoCartao(this.cartao()));
  protected readonly titulo = computed(() => normalizarTitulo(this.cartao().objeto));
  protected readonly itens = computed(() => this.cartao().itens.slice(0, MAX_ITENS));
  protected readonly itensOcultos = computed(() =>
    Math.max(this.cartao().itens.length - MAX_ITENS, 0),
  );
  protected readonly valorGanho = computed(() => moeda(this.cartao().valor_ganho));
  /** O prazo só importa enquanto a proposta ainda pode ser cadastrada. */
  protected readonly prazo = computed(() =>
    this.cartao().estagio === 'preparar'
      ? formatarData(this.cartao().data_encerramento_proposta)
      : null,
  );
  protected readonly resumoDoItem = resumoDoItem;
}
