import { ComponentFixture, TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { of, throwError } from 'rxjs';

import { EncerradaResponse } from '../../../contracts/licitacoes/encerrada.contracts';
import { EncerradasService } from '../../../services/licitacoes/encerradas.service';
import { ModalService } from '../../../shared/overlay/modal.service';
import { CotadorModalComponent } from '../../oportunidades/cotador-modal/cotador-modal.component';
import { EncerradasPage } from './encerradas.page';
import { ProcessoModalComponent } from './processo-modal/processo-modal.component';

const COTADA: EncerradaResponse = {
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
  data_encerramento_proposta: '2026-09-14',
  valor_total_estimado: 400000,
  plataforma_id: 'compras_gov',
  plataforma_nome: 'Compras.gov.br',
  link_plataforma: '',
  link_pncp: '',
  capag: null,
  itens: [],
  expirada: true,
  salva_por: 'Vasti',
  criada_em: '2026-08-31T12:00:00Z',
  encerrada_em: '2026-09-14',
  motivo: 'prazo_cotacao',
  motivo_label: 'Prazo perdido na cotação',
  cotacao_id: 2,
  valor_cotado: 351296.23,
  removida_em: null,
  removida_por: null,
};

const SEM_COTACAO: EncerradaResponse = {
  ...COTADA,
  id: 7,
  chave: 'x-2026-1',
  motivo: 'prazo_cotacao',
  motivo_label: 'Prazo perdido na cotação',
  cotacao_id: null,
  valor_cotado: null,
  removida_por: null,
};

describe('EncerradasPage', () => {
  let fixture: ComponentFixture<EncerradasPage>;
  let service: { listar: ReturnType<typeof vi.fn> };
  let modal: { abrir: ReturnType<typeof vi.fn> };

  function montar() {
    TestBed.configureTestingModule({
      imports: [EncerradasPage],
      providers: [
        { provide: EncerradasService, useValue: service },
        { provide: ModalService, useValue: modal },
      ],
    });
    fixture = TestBed.createComponent(EncerradasPage);
    fixture.detectChanges();
  }

  function pagina() {
    return fixture.componentInstance as never as {
      acoesDe: (l: EncerradaResponse) => { rotulo: string; executar: () => void }[];
      filtros: { patchValue: (v: object) => void };
      pesquisar: () => void;
    };
  }

  beforeEach(() => {
    service = {
      listar: vi.fn(() =>
        of({ count: 2, next: null, previous: null, results: [COTADA, SEM_COTACAO] }),
      ),
    };
    modal = { abrir: vi.fn(() => of(undefined)) };
  });

  it('abre consultando o período padrão, mais recentes primeiro', () => {
    montar();

    const params = service.listar.mock.calls[0][0];
    expect(params.ordering).toBe('-encerrada_em');
    expect(params.data_inicial).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(params.data_final).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(fixture.debugElement.queryAll(By.css('tbody tr'))).toHaveLength(2);
  });

  it('pesquisar manda os filtros e volta para a primeira página', () => {
    montar();
    pagina().filtros.patchValue({ motivo: 'prazo_cotacao', uf: 'PR' });
    pagina().pesquisar();

    expect(service.listar).toHaveBeenLastCalledWith(
      expect.objectContaining({ motivo: 'prazo_cotacao', uf: 'PR', page: 1 }),
    );
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
    expect(modal.abrir.mock.calls[1][1]).toEqual(expect.objectContaining({ oportunidadeId: 4 }));
  });

  it('erro ao carregar mostra a mensagem', () => {
    service.listar.mockReturnValue(throwError(() => new Error('falhou')));
    montar();

    expect(fixture.debugElement.query(By.css('.erro'))).not.toBeNull();
  });
});
