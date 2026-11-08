import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { TorreResponse } from '../../contracts/licitacoes/torre.contracts';
import { ApiClient } from '../../core/api/api-client';
import { ENDPOINTS } from '../../core/api/endpoints';

/** A Torre de Controle — só leitura: a etapa anda com os fatos (Sentinela,
 * PNCP, Portal da Transparência, lançamentos), nunca arrastando cartão. */
@Injectable({ providedIn: 'root' })
export class TorreService {
  private readonly api = inject(ApiClient);

  torre(): Observable<TorreResponse> {
    return this.api.get<TorreResponse>(ENDPOINTS.licitacoes.torre);
  }
}
