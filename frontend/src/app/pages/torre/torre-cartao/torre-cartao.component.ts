import { Component, computed, input, output } from '@angular/core';

import { CartaoTorre } from '../../../contracts/licitacoes/torre.contracts';
import { IconComponent } from '../../../shared/ui/icon/icon.component';
import {
  compraDoCartao,
  ganhandoDoCartao,
  linhaDoCartao,
  localDoCartao,
  nivelDoCartao,
  orgaoDoCartao,
  perdendoDoCartao,
  prazoDoCartao,
  trilhaDoCartao,
} from '../torre.utils';

/**
 * Um cartão da Torre, como no protótipo "Licita v1.0": a etapa (pílula com a
 * cor do estágio), a UASG, o órgão, a compra ("Pregão 61/2026 · item 22"),
 * a posição e o valor numa linha, a trilha das próximas etapas e as
 * etiquetas. O objeto fica no título (passar o mouse). Clicar emite `abrir`
 * — quem decide o que abrir é `TorreAcoesService`.
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
  /** A lixeira (Preparar e Disputar). Quem decide o que fazer é
   * `TorreAcoesService.descartar`. */
  readonly descartar = output<CartaoTorre>();

  protected readonly temLixeira = computed(() =>
    ['preparar', 'disputar'].includes(this.cartao().estagio),
  );

  /** Dentro da coluna da etapa (estágio aberto) a pílula repetiria o nome
   * da coluna: lá ela some, como no protótipo v2. */
  readonly semEtapa = input(false);

  protected readonly nivel = computed(() => nivelDoCartao(this.cartao()));
  protected readonly local = computed(() => localDoCartao(this.cartao()));
  protected readonly orgao = computed(() => orgaoDoCartao(this.cartao()));
  protected readonly compra = computed(() => compraDoCartao(this.cartao()));
  protected readonly linha = computed(() => linhaDoCartao(this.cartao()));
  protected readonly perdendo = computed(() => perdendoDoCartao(this.cartao()));
  protected readonly ganhando = computed(() => ganhandoDoCartao(this.cartao()));
  protected readonly trilha = computed(() => trilhaDoCartao(this.cartao()));
  protected readonly prazo = computed(() => prazoDoCartao(this.cartao()));
}
