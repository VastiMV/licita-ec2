import { Injectable, inject } from '@angular/core';
import { EMPTY, Observable, concatMap, of } from 'rxjs';

import { CartaoTorre } from '../../contracts/licitacoes/torre.contracts';
import { OportunidadeSalvaResponse } from '../../contracts/licitacoes/oportunidade-salva.contracts';
import { ModalService } from '../../shared/overlay/modal.service';
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
