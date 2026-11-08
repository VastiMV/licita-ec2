import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';

import { TorreService } from '../../services/licitacoes/torre.service';
import { TorreAcoesService } from './torre-acoes.service';
import { TorrePage } from './torre.page';
import { PMDF, torre } from './torre.testing';

describe('TorrePage', () => {
  let fixture: ComponentFixture<TorrePage>;
  let servico: { torre: ReturnType<typeof vi.fn> };
  let acoes: { abrir: ReturnType<typeof vi.fn> };

  function montar(resposta = of(torre())): HTMLElement {
    servico = { torre: vi.fn(() => resposta) };
    acoes = { abrir: vi.fn(() => of(true)) };
    TestBed.configureTestingModule({
      imports: [TorrePage],
      providers: [
        provideRouter([]),
        { provide: TorreService, useValue: servico },
        { provide: TorreAcoesService, useValue: acoes },
      ],
    });
    fixture = TestBed.createComponent(TorrePage);
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  it('os 4 estágios lado a lado, na ordem, com o total', () => {
    const el = montar();

    const titulos = Array.from(el.querySelectorAll('.estagio h2')).map((h) =>
      h.textContent?.trim(),
    );
    expect(titulos).toEqual(['Preparar', 'Disputar', 'Contratar', 'Receber']);
    const totais = Array.from(el.querySelectorAll('.estagio .total')).map((t) =>
      t.textContent?.trim(),
    );
    expect(totais).toEqual(['1', '2', '0', '0']);
    expect(el.querySelector('h1')?.textContent).toContain('Torre de Controle');
  });

  it('as etapas em miniatura levam às listas, e o estágio abre por inteiro', () => {
    const el = montar();

    const disputar = el.querySelectorAll('.estagio')[1];
    const etapas = Array.from(disputar.querySelectorAll('.etapas a')) as HTMLAnchorElement[];
    expect(etapas.map((a) => a.getAttribute('href'))).toContain(
      '/torre/etapa/aguardando_julgamento',
    );
    expect(etapas.find((a) => a.textContent?.includes('Disputa'))?.classList.contains('zero')).toBe(
      true,
    );
    expect(
      (disputar.querySelector('.abrir-estagio') as HTMLAnchorElement).getAttribute('href'),
    ).toBe('/torre/estagio/disputar');
  });

  it('estágio vazio diz que está vazio; as saídas levam a Encerradas e Descartadas', () => {
    const el = montar();

    expect(el.querySelectorAll('.estagio')[2].querySelector('.vazio')?.textContent).toContain(
      'Contratar',
    );
    expect(el.querySelector('.saidas')?.textContent).toContain('3 encerradas');
    expect(el.querySelector('.saidas')?.textContent).toContain('8 descartadas');
  });

  it('clicar num cartão chama as ações e recarrega quando pedem', () => {
    const el = montar();

    const cartoes = el.querySelectorAll('.estagio')[1].querySelectorAll('.cartao-abrir');
    (cartoes[1] as HTMLButtonElement).click();

    expect(acoes.abrir).toHaveBeenCalledWith(PMDF);
    expect(servico.torre).toHaveBeenCalledTimes(2);
  });

  it('erro ao carregar mostra o aviso e deixa tentar de novo', () => {
    const el = montar(throwError(() => new Error('fora do ar')));

    expect(el.querySelector('.falha')?.textContent).toContain('Não foi possível carregar a Torre');
  });
});
