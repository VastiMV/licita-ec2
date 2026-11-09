import { DIALOG_DATA, DialogRef } from '@angular/cdk/dialog';
import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';

import {
  ItemDoRelatorio,
  RelatorioResponse,
} from '../../../contracts/licitacoes/relatorio.contracts';
import { EncerradasService } from '../../../services/licitacoes/encerradas.service';
import { RelatorioModalComponent, textoDaDiferenca } from './relatorio-modal.component';

/** Cubatão 55/2026, item 2 (HAR de 08/11/2026), resumido. */
const ITEM: ItemDoRelatorio = {
  numero: '2',
  descricao: 'CADEIRA DE RODAS',
  quantidade: '1.0000',
  participantes: 3,
  lido_em: '2026-11-08T23:50:58Z',
  homologado: false,
  empresa_venceu: null,
  acompanhado: false,
  vencedor: {
    classificacao: 1,
    fornecedor: 'VL-LOJA DE VARIEDADES LTDA',
    cnpj: '35569716000199',
    uf: 'SP',
    marca: 'Prolife',
    modelo: 'P1',
    valor: '825.04',
    situacao: '4',
    caiu: false,
    da_empresa: false,
    atipica: false,
  },
  empresa: {
    classificacao: 23,
    posicao_efetiva: 23,
    marca: 'Dellamed',
    modelo: 'D600',
    valor: '1200.00',
  },
  diferenca: '374.96',
  diferenca_percentual: '45.4',
  mediana: '1100.00',
  marcas: [{ marca: 'DELLAMED', propostas: 18 }],
  propostas: [],
};

const RELATORIO: RelatorioResponse = {
  id: 1,
  compra: 'Pregão 55/2026',
  orgao_nome: 'PREFEITURA DE CUBATAO',
  uasg: '986371',
  objeto: '',
  itens: [
    {
      ...ITEM,
      propostas: [
        ITEM.vencedor!,
        {
          ...ITEM.vencedor!,
          classificacao: 23,
          fornecedor: 'INSIDE SOLUTIONS LTDA',
          da_empresa: true,
          situacao: '',
        },
        {
          ...ITEM.vencedor!,
          classificacao: 31,
          fornecedor: 'CH TREVISAN',
          valor: '199733.32',
          atipica: true,
          situacao: '',
        },
      ],
    },
    { ...ITEM, numero: '5', participantes: 0, vencedor: null, propostas: [] },
  ],
  resumo: { itens: 2, com_propostas: 1, ganhos: 0, perdidos: 0, acompanhados: 0 },
};

describe('RelatorioModalComponent', () => {
  function montar(): HTMLElement {
    TestBed.configureTestingModule({
      imports: [RelatorioModalComponent],
      providers: [
        { provide: DIALOG_DATA, useValue: { id: 1, titulo: 'Pregão 55/2026' } },
        { provide: DialogRef, useValue: { close: vi.fn() } },
        { provide: EncerradasService, useValue: { relatorio: () => of(RELATORIO) } },
      ],
    });
    const fixture = TestBed.createComponent(RelatorioModalComponent);
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  it('mostra o 1º, a Inside e a diferença', () => {
    const el = montar();

    const blocos = [...el.querySelectorAll('.bloco')].map((b) => b.textContent ?? '');
    expect(blocos[0]).toContain('Em 1º lugar');
    expect(blocos[0]).toContain('VL-LOJA DE VARIEDADES LTDA');
    expect(blocos[0]).toContain('Prolife');
    expect(blocos[1]).toContain('23º lugar');
    expect(blocos[2]).toContain('R$ 374,96 acima (45,4%)');
    expect(blocos[2]).toContain('DELLAMED (18)');
  });

  it('marca a linha da empresa e o valor fora do padrão', () => {
    const el = montar();

    expect(el.querySelector('tr.empresa')?.textContent).toContain('INSIDE SOLUTIONS');
    expect(el.querySelector('.atipica')?.textContent).toContain('valor fora do padrão');
  });

  it('item sem propostas lidas explica que a Sentinela ainda vai ler', () => {
    const el = montar();

    expect(el.textContent).toContain('A Sentinela ainda não leu as propostas deste item');
  });

  it('diferença abaixo e igual', () => {
    expect(textoDaDiferenca({ ...ITEM, diferenca: '-12.00', diferenca_percentual: '-1.2' })).toBe(
      'R$ 12,00 abaixo (1,2%)',
    );
    expect(textoDaDiferenca({ ...ITEM, diferenca: '0.00' })).toBe('mesmo valor do vencedor');
    expect(textoDaDiferenca({ ...ITEM, diferenca: null })).toBeNull();
  });
});
