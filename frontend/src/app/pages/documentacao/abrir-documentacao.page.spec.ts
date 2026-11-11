import { TestBed } from '@angular/core/testing';
import { Observable, of, throwError } from 'rxjs';

import { ApiClient } from '../../core/api/api-client';
import { ENDPOINTS } from '../../core/api/endpoints';
import { AbrirDocumentacaoPage, Navegador } from './abrir-documentacao.page';

describe('AbrirDocumentacaoPage', () => {
  function montar(resposta: Observable<unknown>) {
    const api = { post: vi.fn(() => resposta) };
    const assign = vi.fn();
    TestBed.configureTestingModule({
      providers: [
        { provide: ApiClient, useValue: api },
        { provide: Navegador, useValue: { ir: assign } },
      ],
    });
    const fixture = TestBed.createComponent(AbrirDocumentacaoPage);
    fixture.detectChanges();
    return { fixture, api, assign };
  }

  it('pede o passe e vai para o site da documentação', () => {
    const { api, assign } = montar(of(undefined));

    expect(api.post).toHaveBeenCalledWith(ENDPOINTS.auth.documentacao, {});
    expect(assign).toHaveBeenCalledWith('/documentacao/');
  });

  it('se o servidor recusar, avisa e não sai da tela', () => {
    const { fixture, assign } = montar(throwError(() => new Error('401')));
    fixture.detectChanges();

    expect(assign).not.toHaveBeenCalled();
    expect(fixture.nativeElement.textContent).toContain('Não foi possível abrir a documentação');
  });
});
