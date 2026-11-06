import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import {
  DescartadasPagina,
  DescartadasParams,
} from '../../contracts/licitacoes/descartada.contracts';
import {
  EncerradasPagina,
  EncerradasParams,
  ProcessoResponse,
} from '../../contracts/licitacoes/encerrada.contracts';
import { ApiClient } from '../../core/api/api-client';
import { ENDPOINTS } from '../../core/api/endpoints';

@Injectable({ providedIn: 'root' })
export class EncerradasService {
  private readonly api = inject(ApiClient);

  listar(params: EncerradasParams = {}): Observable<EncerradasPagina> {
    return this.api.get<EncerradasPagina>(ENDPOINTS.licitacoes.encerradas, { ...params });
  }

  /** As tiradas da lista antes do prazo (tela Descartadas). */
  descartadas(params: DescartadasParams = {}): Observable<DescartadasPagina> {
    return this.api.get<DescartadasPagina>(ENDPOINTS.licitacoes.descartadas, { ...params });
  }

  /** A história da salva no formato do modal do processo. */
  processo(id: number): Observable<ProcessoResponse> {
    return this.api.get<ProcessoResponse>(ENDPOINTS.licitacoes.processo(id));
  }
}
