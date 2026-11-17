import { ComponentFixture, TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { of } from 'rxjs';

import { SugestaoRadarResponse } from '../../contracts/licitacoes/radar.contracts';
import { RadarService } from '../../services/licitacoes/radar.service';
import { ModalService } from '../../shared/overlay/modal.service';
import { ToastService } from '../../shared/ui/toast/toast.service';
import { RadarPage } from './radar.page';
import { RadarModalComponent } from './radar-modal/radar-modal.component';

const SUGESTAO: SugestaoRadarResponse = {
  id: 3,
  chave: '1-2026-10',
  cnpj_orgao: '1',
  ano_compra: '2026',
  sequencial_compra: '10',
  objeto: 'Aquisição de ração',
  orgao_nome: 'Prefeitura de Teste',
  uasg: '',
  uf: 'MG',
  municipio: 'Cidade',
  modalidade: 'Pregão - Eletrônico',
  data_publicacao: '2026-11-13',
  data_encerramento_proposta: '2026-11-25',
  valor_total_estimado: 100,
  plataforma_id: '',
  link_plataforma: 'https://www.portaldecompraspublicas.com.br/processos/1',
  link_pncp: '',
  itens: [],
  parecido_com: 'Luva de procedimento',
  por_ganho: true,
  encontrada_em: '2026-11-14T11:00:00Z',
  expira_em: '2026-11-21',
};

describe('RadarPage', () => {
  let fixture: ComponentFixture<RadarPage>;
  let service: { listar: ReturnType<typeof vi.fn>; remover: ReturnType<typeof vi.fn> };
  let modal: { abrir: ReturnType<typeof vi.fn> };

  beforeEach(() => {
    service = {
      listar: vi.fn(() => of({ count: 1, next: null, previous: null, results: [SUGESTAO] })),
      remover: vi.fn(() => of(undefined)),
    };
    modal = { abrir: vi.fn(() => of('salva')) };
    TestBed.configureTestingModule({
      imports: [RadarPage],
      providers: [
        { provide: RadarService, useValue: service },
        { provide: ModalService, useValue: modal },
        { provide: ToastService, useValue: { sucesso: vi.fn(), erro: vi.fn() } },
      ],
    });
    fixture = TestBed.createComponent(RadarPage);
    fixture.detectChanges();
  });

  it('mostra a sugestão e de onde ela veio', () => {
    const texto = fixture.nativeElement.textContent;
    expect(fixture.debugElement.queryAll(By.css('tbody tr'))).toHaveLength(1);
    expect(texto).toContain('Luva de procedimento');
    expect(texto).toContain('a Inside ganhou');
  });

  it('filtrar por UF manda a UF e volta para a primeira página', () => {
    (fixture.componentInstance as never as { uf: { setValue: (v: string) => void } }).uf.setValue('MG');

    expect(service.listar.mock.lastCall![0]).toEqual(expect.objectContaining({ uf: 'MG', page: 1 }));
  });

  it('clicar abre o card; salvar recarrega a lista', () => {
    fixture.debugElement.query(By.css('tbody tr')).nativeElement.click();

    expect(modal.abrir.mock.calls[0][0]).toBe(RadarModalComponent);
    expect(modal.abrir.mock.calls[0][1]).toBe(SUGESTAO);
    expect(service.listar).toHaveBeenCalledTimes(2);
  });

  it('a lixeira remove sem perguntar e recarrega, sem abrir o card (GEN-93)', () => {
    fixture.debugElement.query(By.css('button.lixeira')).nativeElement.click();

    expect(service.remover).toHaveBeenCalledWith(3);
    expect(modal.abrir).not.toHaveBeenCalled();
    expect(service.listar).toHaveBeenCalledTimes(2);
  });
});
