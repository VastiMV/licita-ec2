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
            relatorioMercado: () =>
              of([
                {
                  descricao: 'Cadeira De Rodas Manual Para Locomoção, capacidade: de 171 a 200',
                  nome_pdm: 'CADEIRA DE RODAS MANUAL PARA LOCOMOÇÃO',
                  codigo_catmat: 637928,
                  exato: {
                    '3': { compras: 0, media: null, marcas: [], poucos_dados: true },
                    '6': { compras: 4, media: 1278.09, marcas: [], poucos_dados: false },
                    '12': { compras: 4, media: 1278.09, marcas: [], poucos_dados: false },
                    '24': {
                      compras: 4,
                      media: 1278.09,
                      marcas: [{ marca: 'DELLAMED', vezes: 3 }],
                      poucos_dados: false,
                    },
                  },
                  grupo: {
                    '12': { compras: 179, media: 1496.51, marcas: [], poucos_dados: false },
                  },
                  media_dele: 1200,
                  ofertas_dele: 1,
                  atualizado_em: null,
                },
              ]),
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

  it('o mercado de cada item: barras, a oferta dele, marcas e a referência do tipo', () => {
    const el = montar();

    const bloco = el.querySelector('.mercado')?.textContent ?? '';
    expect(el.querySelectorAll('.barra').length).toBe(4);
    expect(bloco).toContain('R$\u00a01.278,09');
    expect(bloco).toContain('Você ofereceu em média: R$\u00a01.200,00');
    expect(bloco).toContain('DELLAMED');
    expect(bloco).toContain('179 compras');
  });

  it('nome do mês', () => {
    expect(nomeDoMes('2026-10')).toBe('out/2026');
  });
});
