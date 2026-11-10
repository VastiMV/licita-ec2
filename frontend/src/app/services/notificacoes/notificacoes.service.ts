import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { NotificacoesResponse } from '../../contracts/notificacoes/notificacoes.contracts';
import { ApiClient } from '../../core/api/api-client';
import { ENDPOINTS } from '../../core/api/endpoints';

@Injectable({ providedIn: 'root' })
export class NotificacoesService {
  private readonly api = inject(ApiClient);

  listar(): Observable<NotificacoesResponse> {
    return this.api.get<NotificacoesResponse>(ENDPOINTS.notificacoes.lista);
  }

  /** Sem ids: todas. */
  marcarLidas(ids?: readonly number[]): Observable<unknown> {
    return this.api.post<unknown>(ENDPOINTS.notificacoes.lidas, ids ? { ids } : {});
  }

  /** Manda uma mensagem de teste para o Telegram de cada pessoa cadastrada. */
  testarTelegram(): Observable<{ ligado: boolean; enviados: number; chats: number }> {
    return this.api.post<{ ligado: boolean; enviados: number; chats: number }>(
      ENDPOINTS.notificacoes.testeTelegram,
      {},
    );
  }
}
