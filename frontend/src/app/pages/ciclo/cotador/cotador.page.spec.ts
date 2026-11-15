import { ComponentFixture, TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { of, throwError } from 'rxjs';

import { EmCotacaoResponse } from '../../../contracts/licitacoes/em-cotacao.contracts';
import { CotadorService } from '../../../services/cotador/cotador.service';
import { EmCotacaoService } from '../../../services/licitacoes/em-cotacao.service';
import { PropostasService } from '../../../services/propostas/propostas.service';
import { ModalService } from '../../../shared/overlay/modal.service';
import { ToastService } from '../../../shared/ui/toast/toast.service';
import { CotadorModalComponent } from '../../oportunidades/cotador-modal/cotador-modal.component';
import { CotadorPage } from './cotador.page';

const LINHA: EmCotacaoResponse = {
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
  data_encerramento_proposta: '2026-10-14',
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
  cotacao_id: 2,
  valor_cotado: 351296.23,
  cotacao_atualizada_em: '2026-09-02T12:00:00Z',
  pendencias: 1,
  selo: { nivel: 'aviso', texto: '1 item sem preço', faltas: ['preço de fornecedor no item 3'] },
};

describe('CotadorPage', () => {
  let fixture: ComponentFixture<CotadorPage>;
  let service: { listar: ReturnType<typeof vi.fn> };
  let cotador: { remover: ReturnType<typeof vi.fn> };
  let propostas: { gerar: ReturnType<typeof vi.fn> };
  let modal: { abrir: ReturnType<typeof vi.fn>; confirmar: ReturnType<typeof vi.fn> };

  function montar() {
    TestBed.configureTestingModule({
      imports: [CotadorPage],
      providers: [
        { provide: EmCotacaoService, useValue: service },
        { provide: CotadorService, useValue: cotador },
        { provide: PropostasService, useValue: propostas },
        { provide: ModalService, useValue: modal },
        { provide: ToastService, useValue: { sucesso: vi.fn(), erro: vi.fn() } },
      ],
    });
    fixture = TestBed.createComponent(CotadorPage);
    fixture.detectChanges();
  }

  function pagina() {
    return fixture.componentInstance as never as {
      acoesDe: (l: EmCotacaoResponse) => { rotulo: string; executar: () => void }[];
    };
  }

  beforeEach(() => {
    service = {
      listar: vi.fn(() => of({ count: 1, next: null, previous: null, results: [LINHA] })),
    };
    cotador = { remover: vi.fn(() => of(undefined)) };
    propostas = { gerar: vi.fn(() => of({})) };
    modal = { abrir: vi.fn(() => of(undefined)), confirmar: vi.fn(() => of(true)) };
  });

  it('abre com o prazo mais próximo primeiro e mostra a situação', () => {
    montar();

    expect(service.listar.mock.calls[0][0].ordering).toBe('prazo');
    expect(fixture.debugElement.queryAll(By.css('tbody tr'))).toHaveLength(1);
    expect(fixture.nativeElement.textContent).toContain('1 item sem preço');
  });

  it('abrir cotação abre o Cotador da oportunidade', () => {
    montar();

    pagina().acoesDe(LINHA)[0].executar();

    expect(modal.abrir.mock.calls[0][0]).toBe(CotadorModalComponent);
    expect(modal.abrir.mock.calls[0][1]).toEqual(expect.objectContaining({ oportunidadeId: 4 }));
  });

  it('as ações são abrir cotação, gerar proposta e excluir cotação — sem "ver processo"', () => {
    montar();

    expect(
      pagina()
        .acoesDe(LINHA)
        .map((a) => a.rotulo),
    ).toEqual(['Abrir cotação', 'Gerar proposta', 'Excluir cotação']);
  });

  it('gerar proposta confirmado gera e recarrega a lista', () => {
    montar();

    pagina().acoesDe(LINHA)[1].executar();

    expect(modal.confirmar.mock.calls[0][0].mensagem).toContain('item 3');
    expect(propostas.gerar).toHaveBeenCalledWith(4);
    expect(service.listar).toHaveBeenCalledTimes(2);
  });

  it('gerar proposta cancelado não gera', () => {
    modal.confirmar.mockReturnValue(of(false));
    montar();

    pagina().acoesDe(LINHA)[1].executar();

    expect(propostas.gerar).not.toHaveBeenCalled();
  });

  it('excluir confirmado apaga a cotação e recarrega', () => {
    montar();

    pagina().acoesDe(LINHA)[2].executar();

    expect(cotador.remover).toHaveBeenCalledWith(2);
    expect(service.listar).toHaveBeenCalledTimes(2);
  });

  it('preço só no Compras.gov (sem cotação no Licita): aparece e só deixa abrir a cotação', () => {
    const semCotacao: EmCotacaoResponse = {
      ...LINHA,
      cotacao_id: null,
      valor_cotado: null,
      cotacao_atualizada_em: null,
      pendencias: null,
      selo: {
        nivel: 'aviso',
        texto: 'Sem cotação no Licita',
        faltas: ['preço lançado no Compras.gov — abra a cotação para registrar'],
      },
    };
    service.listar.mockReturnValue(of({ count: 1, next: null, previous: null, results: [semCotacao] }));
    montar();

    expect(fixture.nativeElement.textContent).toContain('Sem cotação no Licita');
    expect(
      pagina()
        .acoesDe(semCotacao)
        .map((a) => a.rotulo),
    ).toEqual(['Abrir cotação']);
  });

  it('gerar proposta não diz que muda de etapa (o PDF é o anexo depois de vencer)', () => {
    montar();

    pagina().acoesDe(LINHA)[1].executar();

    expect(modal.confirmar.mock.calls[0][0].mensagem).not.toContain('etapa');
  });

  it('erro ao carregar mostra a mensagem', () => {
    service.listar.mockReturnValue(throwError(() => new Error('falhou')));
    montar();

    expect(fixture.debugElement.query(By.css('.erro'))).not.toBeNull();
  });
});
