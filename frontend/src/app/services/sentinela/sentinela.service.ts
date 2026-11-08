import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { EstadoSentinelaResponse } from '../../contracts/sentinela/sentinela.contracts';
import { ApiClient } from '../../core/api/api-client';
import { ENDPOINTS } from '../../core/api/endpoints';

/** Só leitura: o que a Sentinela disse por último (o vigia do topo). */
@Injectable({ providedIn: 'root' })
export class SentinelaService {
  private readonly api = inject(ApiClient);

  estado(): Observable<EstadoSentinelaResponse> {
    return this.api.get<EstadoSentinelaResponse>(ENDPOINTS.sentinela.estado);
  }
}
