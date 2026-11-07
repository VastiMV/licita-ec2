import { ComponentFixture, TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { of, throwError } from 'rxjs';

import { DescartadaResponse } from '../../../contracts/licitacoes/descartada.contracts';
import { EncerradasService } from '../../../services/licitacoes/encerradas.service';
import { ModalService } from '../../../shared/overlay/modal.service';
import { CotadorModalComponent } from '../../oportunidades/cotador-modal/cotador-modal.component';
import { ProcessoModalComponent } from '../encerradas/processo-modal/processo-modal.component';
import { DescartadasPage, limitesDoMes, ultimosMeses } from './descartadas.page';

const COTADA: DescartadaResponse = {
  id: 4,
  chave: '95422986000102-2026-222',
  cnpj_orgao: '95422986000102',
  ano_compra: '2026',
  sequencial_compra: '222',
  objeto: 'Equipamentos médico hospitalares',
  orgao_nome: 'Prefeitura de Fazenda Rio Grande',
  uasg: '989983',
  uf: 'PR',
  municipio: 'Fazenda Rio Grande',
  modalidade: 'Pregão Eletrônico',
  situacao: 'Divulgada no PNCP',
  data_publicacao: '2026-08-20',
  data_encerramento_proposta: '2026-12-14',
  valor_total_estimado: 400000,
  plataforma_id: 'compras_gov',
  plataforma_nome: 'Compras.gov.br',
  link_plataforma: '',
  link_pncp: '',
  capag: null,
  itens: [],
  expirada: false,
  salva_por: 'Vasti',
  criada_em: '2026-08-31T12:00:00Z',
  descartada_em: '2026-11-05',
  motivo: 'descartada',
  motivo_label: 'Tirada da lista',
  estava_em: 'cotacao',
  cotacao_id: 2,
  valor_cotado: 351296.23,
  removida_em: '2026-11-05T14:30:00Z',
  removida_por: 'Carlinhos',
};

const SEM_COTACAO: DescartadaResponse = {
  ...COTADA,
  id: 7,
  chave: 'x-2026-1',
  motivo: 'prazo_oportunidade',
  motivo_label: 'Prazo venceu sem cotação',
  removida_em: null,
  removida_por: null,
  estava_em: 'oportunidade',
  cotacao_id: null,
  valor_cotado: null,
};

describe('DescartadasPage', () => {
  let fixture: ComponentFixture<DescartadasPage>;
  let service: { descartadas: ReturnType<typeof vi.fn> };
  let modal: { abrir: ReturnType<typeof vi.fn> };

  function montar() {
    TestBed.configureTestingModule({
      imports: [DescartadasPage],
      providers: [
        { provide: EncerradasService, useValue: service },
        { provide: ModalService, useValue: modal },
      ],
    });
    fixture = TestBed.createComponent(DescartadasPage);
    fixture.detectChanges();
  }

  function pagina() {
    return fixture.componentInstance as never as {
      acoesDe: (l: DescartadaResponse) => { rotulo: string; executar: () => void }[];
      filtros: { patchValue: (v: object) => void };
      pesquisar: () => void;
    };
  }

  beforeEach(() => {
    service = {
      descartadas: vi.fn(() =>
        of({ count: 2, next: null, previous: null, results: [COTADA, SEM_COTACAO] }),
      ),
    };
    modal = { abrir: vi.fn(() => of(undefined)) };
  });

  it('abre consultando o período padrão, descarte mais recente primeiro', () => {
    montar();

    const params = service.descartadas.mock.calls[0][0];
    expect(params.ordering).toBe('-descartada_em');
    expect(params.data_inicial).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(fixture.debugElement.queryAll(By.css('tbody tr'))).toHaveLength(2);
  });

  it('mostra o motivo, quem descartou e onde a licitação estava', () => {
    montar();

    const [tirada, prazo] = fixture.debugElement
      .queryAll(By.css('tbody tr'))
      .map((linha) => linha.nativeElement.textContent as string);
    expect(tirada).toContain('Tirada da lista');
    expect(tirada).toContain('por Carlinhos');
    expect(tirada).toContain('Cotação');
    expect(prazo).toContain('Prazo venceu sem cotação');
    expect(prazo).not.toContain('por ');
  });

  it('pesquisar manda os filtros e volta para a primeira página', () => {
    montar();
    pagina().filtros.patchValue({ motivo: 'prazo_oportunidade', uasg: '925001', uf: 'PR' });
    pagina().pesquisar();

    expect(service.descartadas).toHaveBeenLastCalledWith(
      expect.objectContaining({
        motivo: 'prazo_oportunidade',
        uasg: '925001',
        uf: 'PR',
        page: 1,
      }),
    );
  });

  it('escolher um mês preenche "de" e "até" e o mês não vai para a API', () => {
    montar();
    pagina().filtros.patchValue({ mes: '2026-02' });
    pagina().pesquisar();

    const params = service.descartadas.mock.lastCall![0];
    expect(params).toEqual(
      expect.objectContaining({ data_inicial: '2026-02-01', data_final: '2026-02-28' }),
    );
    expect(params).not.toHaveProperty('mes');
  });

  it('motivo é texto normal, sem destaque em vermelho', () => {
    montar();

    expect(
      fixture.debugElement.queryAll(By.css('tbody .perigo, tbody [class*="perigo"]')),
    ).toHaveLength(0);
  });

  it('"Ver cotação" só aparece para quem chegou a cotar', () => {
    montar();

    expect(
      pagina()
        .acoesDe(COTADA)
        .map((a) => a.rotulo),
    ).toEqual(['Ver processo', 'Ver cotação']);
    expect(
      pagina()
        .acoesDe(SEM_COTACAO)
        .map((a) => a.rotulo),
    ).toEqual(['Ver processo']);
  });

  it('ver processo abre o modal do processo; pedir a cotação de lá abre o Cotador', () => {
    modal.abrir.mockReturnValueOnce(of('cotacao'));
    montar();

    pagina().acoesDe(COTADA)[0].executar();

    expect(modal.abrir.mock.calls[0][0]).toBe(ProcessoModalComponent);
    expect(modal.abrir.mock.calls[1][0]).toBe(CotadorModalComponent);
  });

  it('erro ao carregar mostra a mensagem', () => {
    service.descartadas.mockReturnValue(throwError(() => new Error('falhou')));
    montar();

    expect(fixture.debugElement.query(By.css('.erro'))).not.toBeNull();
  });
});

describe('meses do filtro', () => {
  it('lista os últimos 12 meses, virando o ano', () => {
    const meses = ultimosMeses('2026-02-15');

    expect(meses).toHaveLength(12);
    expect(meses[0]).toEqual({ value: '2026-02', label: 'fevereiro de 2026' });
    expect(meses[2]).toEqual({ value: '2025-12', label: 'dezembro de 2025' });
  });

  it('acha o último dia do mês, inclusive fevereiro bissexto', () => {
    expect(limitesDoMes('2028-02')).toEqual({ inicio: '2028-02-01', fim: '2028-02-29' });
    expect(limitesDoMes('2026-11')).toEqual({ inicio: '2026-11-01', fim: '2026-11-30' });
  });
});
