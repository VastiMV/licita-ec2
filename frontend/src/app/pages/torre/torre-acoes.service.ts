import { Injectable, inject } from '@angular/core';
import { EMPTY, Observable, catchError, concatMap, map, of } from 'rxjs';

import { CartaoTorre } from '../../contracts/licitacoes/torre.contracts';
import { OportunidadeSalvaResponse } from '../../contracts/licitacoes/oportunidade-salva.contracts';
import { TorreService } from '../../services/licitacoes/torre.service';
import { ModalService } from '../../shared/overlay/modal.service';
import { ToastService } from '../../shared/ui/toast/toast.service';
import {
  CotadorModalComponent,
  CotadorModalData,
} from '../oportunidades/cotador-modal/cotador-modal.component';
import { normalizarTitulo } from '../oportunidades/edital-card/edital-card.utils';
import {
  OportunidadeModalComponent,
  OportunidadeModalResultado,
} from '../oportunidades/salvas/oportunidade-modal/oportunidade-modal.component';

/**
 * O que acontece ao clicar num cartão da Torre — num lugar só, para o
 * quadro, o estágio aberto e as listas fazerem o mesmo.
 *
 * Em Preparar, os modais que já existem: Oportunidade abre o visualizador da
 * salva (que tem "Iniciar cotação"); com cotação, abre o Cotador. Dali em
 * diante a licitação vive no Compras.gov.br: o cartão abre a compra lá.
 *
 * Devolve um Observable que termina quando o modal fecha — é a deixa para a
 * tela recarregar a Torre. Abrir o Compras.gov.br não pede recarga.
 */
@Injectable({ providedIn: 'root' })
export class TorreAcoesService {
  private readonly modal = inject(ModalService);
  private readonly torre = inject(TorreService);
  private readonly toast = inject(ToastService);

  /**
   * A lixeira (decisão da operação, 08/11/2026): uma pergunta só, mostrando
   * o preço lançado quando houver, e a licitação vai para Descartadas com o
   * motivo completo; no Compras.gov, a Sentinela tira o favorito.
   * `true` quando a tela deve recarregar.
   */
  descartar(cartao: CartaoTorre): Observable<boolean> {
    return this.torre.resumoDoDescarte(cartao.id).pipe(
      concatMap((resumo) =>
        this.modal.confirmar({
          titulo: `Descartar ${cartao.compra}?`,
          mensagem:
            resumo.pergunta +
            (resumo.tira_favorito
              ? ' No Compras.gov, a Sentinela tira o favorito desta compra.'
              : ''),
          confirmarLabel: 'Descartar',
          variantConfirmar: 'danger',
        }),
      ),
      concatMap((confirmou) =>
        confirmou
          ? this.torre.descartar(cartao.id).pipe(
              map(() => {
                this.toast.sucesso(`${cartao.compra} foi para Descartadas.`);
                return true;
              }),
            )
          : of(false),
      ),
      catchError(() => {
        this.toast.erro('Não foi possível descartar agora. Tente de novo.');
        return of(false);
      }),
    );
  }

  /** `true` quando a tela deve recarregar. */
  abrir(cartao: CartaoTorre): Observable<boolean> {
    if (cartao.etapa === 'oportunidade' && cartao.salva) {
      const salva = cartao.salva;
      return this.modal
        .abrir<OportunidadeModalResultado, OportunidadeSalvaResponse>(
          OportunidadeModalComponent,
          salva,
        )
        .pipe(concatMap((resultado) => (resultado === 'cotar' ? this.cotar(cartao) : of(true))));
    }
    if (cartao.cotacao_id !== null && cartao.salva) return this.cotar(cartao);
    if (cartao.link_plataforma) {
      window.open(cartao.link_plataforma, '_blank', 'noopener');
      return of(false);
    }
    return EMPTY;
  }

  private cotar(cartao: CartaoTorre): Observable<boolean> {
    const dados: CotadorModalData = {
      titulo: normalizarTitulo(cartao.objeto),
      itens: cartao.salva?.itens ?? [],
      oportunidadeId: cartao.id,
    };
    return this.modal
      .abrir<unknown, CotadorModalData>(CotadorModalComponent, dados)
      .pipe(concatMap(() => of(true)));
  }
}
