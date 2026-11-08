import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';

import { ApiClient } from '../../core/api/api-client';
import { ENDPOINTS } from '../../core/api/endpoints';
import { TorreService } from './torre.service';

describe('TorreService', () => {
  it('torre() chama GET em licitacoes/torre/', () => {
    const api = { get: vi.fn(() => of({})) };
    TestBed.configureTestingModule({ providers: [{ provide: ApiClient, useValue: api }] });

    TestBed.inject(TorreService).torre().subscribe();

    expect(api.get).toHaveBeenCalledWith(ENDPOINTS.licitacoes.torre);
  });
});
