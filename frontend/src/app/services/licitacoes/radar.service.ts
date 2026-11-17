import { Injectable, inject } from '@angular/core';
import { Observable, map } from 'rxjs';

import {
  RadarPagina,
  RadarParams,
} from '../../contracts/licitacoes/radar.contracts';
import { ApiClient } from '../../core/api/api-client';
import { ENDPOINTS } from '../../core/api/endpoints';

/** O Radar (GEN-68): a lista e o número do botão do topo. */
@Injectable({ providedIn: 'root' })
export class RadarService {
  private readonly api = inject(ApiClient);

  listar(params: RadarParams = {}): Observable<RadarPagina> {
    return this.api.get<RadarPagina>(ENDPOINTS.licitacoes.radar, { ...params });
  }

  /** "Remover do Radar" (GEN-93): sai da lista e não volta. */
  remover(id: number): Observable<void> {
    return this.api.post<void, Record<string, never>>(ENDPOINTS.licitacoes.radarRemover(id), {});
  }

  total(): Observable<number> {
    return this.api
      .get<{ total: number }>(ENDPOINTS.licitacoes.radarTotal)
      .pipe(map((r) => r.total));
  }
}
