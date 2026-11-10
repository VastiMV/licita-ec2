import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';

import { EncerradasService } from '../../services/licitacoes/encerradas.service';
import { RelatoriosPage, nomeDoMes } from './relatorios.page';

describe('RelatoriosPage', () => {
  function montar(): HTMLElement {
    TestBed.configureTestingModule({
      imports: [RelatoriosPage],
      providers: [
        {
          provide: EncerradasService,
          useValue: {
            relatorioMensal: () =>
              of({
                meses: [
                  {
                    mes: '2026-11',
                    participou: 0,
                    ganhou: 0,
                    perdeu: 0,
                    faturamento: '0.00',
                    lucro: null,
                  },
                  {
                    mes: '2026-10',
                    participou: 2,
                    ganhou: 1,
                    perdeu: 1,
                    faturamento: '239980.00',
                    lucro: '39980.00',
                  },
                ],
                por_pouco: [
                  {
                    mes: '2026-10',
                    oportunidade_id: 20,
                    compra: 'Pregão 59/2026',
                    orgao_nome: 'X',
                    item: '30',
                    descricao: '',
                    diferenca: '1.00',
                    diferenca_percentual: '0.1',
                    marca_vencedora: 'DELLAMED',
                  },
                ],
                pouco_percentual: '5',
              }),
          },
        },
      ],
    });
    const f = TestBed.createComponent(RelatoriosPage);
    f.detectChanges();
    return f.nativeElement as HTMLElement;
  }

  it('uma linha por mês e o total', () => {
    const el = montar();

    const linhas = [...el.querySelectorAll('tbody tr')].map((l) => l.textContent ?? '');
    expect(linhas[1]).toContain('out/2026');
    expect(linhas[1]).toContain('R$ 239.980,00');
    expect(linhas[0]).toContain('—');
    expect(el.querySelector('tfoot')?.textContent).toContain('R$ 39.980,00');
  });

  it('"perdeu por pouco" é uma linha só que abre a lista', () => {
    const el = montar();

    expect(el.querySelector('.por-pouco')?.textContent).toContain('1 item');
    expect(el.querySelector('.lista-pouco')).toBeNull();
    (el.querySelector('.por-pouco') as HTMLButtonElement).click();
    TestBed.inject(EncerradasService);
  });

  it('nome do mês', () => {
    expect(nomeDoMes('2026-10')).toBe('out/2026');
  });
});
