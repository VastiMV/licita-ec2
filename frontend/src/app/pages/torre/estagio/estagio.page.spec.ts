import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { of } from 'rxjs';

import { TorreService } from '../../../services/licitacoes/torre.service';
import { TorreAcoesService } from '../torre-acoes.service';
import { torre } from '../torre.testing';
import { EstagioPage } from './estagio.page';

describe('EstagioPage', () => {
  let fixture: ComponentFixture<EstagioPage>;

  function montar(estagio: string): HTMLElement {
    TestBed.configureTestingModule({
      imports: [EstagioPage],
      providers: [
        provideRouter([]),
        { provide: TorreService, useValue: { torre: () => of(torre()) } },
        { provide: TorreAcoesService, useValue: { abrir: () => of(false) } },
        { provide: ActivatedRoute, useValue: { paramMap: of(convertToParamMap({ estagio })) } },
      ],
    });
    fixture = TestBed.createComponent(EstagioPage);
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  it('as etapas do estágio viram colunas, com os cartões de cada uma', () => {
    const el = montar('disputar');

    const colunas = Array.from(el.querySelectorAll('.coluna-topo span')).map((s) =>
      s.textContent?.trim(),
    );
    expect(colunas).toEqual([
      'Disputa',
      'Aguardando julgamento',
      'Julgado e habilitado',
      'Aguardando adjudicação',
    ]);
    const coluna = el.querySelectorAll('.coluna')[1];
    expect(coluna.querySelectorAll('app-torre-cartao').length).toBe(1);
  });

  it('os outros estágios ficam em faixas nas laterais, na ordem do ciclo', () => {
    const el = montar('disputar');
    const palco = Array.from(el.querySelector('.palco')!.children).map((filho) =>
      filho.classList.contains('aberto')
        ? 'ABERTO'
        : `${filho.querySelector('.faixa-nome')?.textContent?.trim()} ${filho.querySelector('.faixa-total')?.textContent?.trim()}`,
    );

    expect(palco).toEqual(['Preparar 1', 'ABERTO', 'Contratar 0', 'Receber 0']);
    const contratar = el.querySelectorAll('a.faixa')[1] as HTMLAnchorElement;
    expect(contratar.getAttribute('href')).toBe('/torre/estagio/contratar');
  });

  it('estágio desconhecido avisa e oferece voltar', () => {
    const el = montar('inexistente');

    expect(el.textContent).toContain('Estágio não encontrado');
  });
});
