import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { of } from 'rxjs';

import { TorreService } from '../../../services/licitacoes/torre.service';
import { TorreAcoesService } from '../torre-acoes.service';
import { PMDF, torre } from '../torre.testing';
import { EtapaPage } from './etapa.page';

describe('EtapaPage', () => {
  let fixture: ComponentFixture<EtapaPage>;
  let acoes: { abrir: ReturnType<typeof vi.fn> };

  function montar(etapa: string): HTMLElement {
    acoes = { abrir: vi.fn(() => of(false)) };
    TestBed.configureTestingModule({
      imports: [EtapaPage],
      providers: [
        provideRouter([]),
        { provide: TorreService, useValue: { torre: () => of(torre()) } },
        { provide: TorreAcoesService, useValue: acoes },
        { provide: ActivatedRoute, useValue: { paramMap: of(convertToParamMap({ etapa })) } },
      ],
    });
    fixture = TestBed.createComponent(EtapaPage);
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  it('lista as licitações da etapa, com os itens e o valor', () => {
    const el = montar('aguardando_adjudicacao');

    expect(el.querySelector('h1')?.textContent).toContain('Aguardando adjudicação');
    const linhas = el.querySelectorAll('tbody tr');
    expect(linhas.length).toBe(1);
    expect(linhas[0].textContent).toContain('UASG 926670');
    expect(linhas[0].textContent).toContain('Item 22 · 1º · Fornecedor habilitado');
    expect(linhas[0].querySelector('.valor')?.textContent).toContain('R$\u00a015.500,00');
    expect(el.querySelector('.caminho')?.textContent).toContain('Disputar');
  });

  it('"Abrir" chama as ações com o cartão', () => {
    const el = montar('aguardando_adjudicacao');

    (el.querySelector('.abrir') as HTMLButtonElement).click();

    expect(acoes.abrir).toHaveBeenCalledWith(PMDF);
  });

  it('etapa sem licitação diz que está vazia', () => {
    const el = montar('homologado');

    expect(el.querySelector('.vazio')?.textContent).toContain('Nenhuma licitação em Homologado');
  });
});
