import { DIALOG_DATA, DialogRef } from '@angular/cdk/dialog';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { of, throwError } from 'rxjs';

import { OportunidadeSalvaResponse } from '../../../../contracts/licitacoes/oportunidade-salva.contracts';
import { OportunidadeResponse } from '../../../../contracts/licitacoes/oportunidade.contracts';
import { LicitacoesService } from '../../../../services/licitacoes/licitacoes.service';
import { OportunidadeModalComponent } from './oportunidade-modal.component';

const ITEM: OportunidadeResponse = {
  numero_item: '1',
  descricao_resumida: 'Café torrado e moído',
  descricao_detalhada: null,
  quantidade: 100,
  unidade_medida: 'PACOTE',
  valor_unitario_estimado: 18.5,
  valor_total: 1850,
  tipo_beneficio: null,
  criterio_julgamento: 'Menor preço',
  contratacao_uf: 'SP',
  contratacao_modalidade: 'Pregão Eletrônico',
  contratacao_srp: false,
  contratacao_situacao: 'Divulgada no PNCP',
  situacao_item: null,
  contratacao_data_publicacao: '2026-08-20',
  contratacao_data_encerramento_proposta: '31/12/2099',
  contratacao_orgao_nome: 'Prefeitura de Campinas',
  contratacao_municipio: 'Campinas',
  contratacao_uasg: '925997',
  contratacao_objeto: 'Aquisição de café e açúcar',
  contratacao_cnpj_orgao: '12345678000199',
  contratacao_ano_compra: '2026',
  contratacao_sequencial_compra: '42',
  plataforma_id: 'compras_gov',
  link_plataforma: 'https://compras.gov.br/compra/1',
  link_pncp: 'https://pncp.gov.br/app/editais/12345678000199/2026/42',
  capag: null,
};

const SALVA: OportunidadeSalvaResponse = {
  id: 1,
  chave: '12345678000199-2026-42',
  cnpj_orgao: '12345678000199',
  ano_compra: '2026',
  sequencial_compra: '42',
  objeto: 'Aquisição de café e açúcar',
  orgao_nome: 'Prefeitura de Campinas',
  uasg: '925997',
  uf: 'SP',
  municipio: 'Campinas',
  modalidade: 'Pregão Eletrônico',
  situacao: 'Divulgada no PNCP',
  data_publicacao: '2026-08-20',
  data_encerramento_proposta: '2099-12-31',
  valor_total_estimado: 1850,
  plataforma_id: 'compras_gov',
  plataforma_nome: 'Compras.gov.br',
  link_plataforma: 'https://compras.gov.br/compra/1',
  link_pncp: 'https://pncp.gov.br/app/editais/12345678000199/2026/42',
  capag: { nota: 'B', cor: 'amarelo' },
  itens: [ITEM],
  expirada: false,
  salva_por: 'Gustavo',
  criada_em: '2026-08-25T12:00:00Z',
};

const DETALHE = {
  documentos: [{ titulo: 'Edital.pdf', tipo_documento: 'Edital', url: 'https://pncp.gov.br/x/1' }],
  capag: { nota: 'A', cor: 'verde' as const },
  plataforma: {
    id: 'compras_gov',
    nome: 'Compras.gov.br',
    link: 'https://compras.gov.br/compra/1',
  },
};

describe('OportunidadeModalComponent', () => {
  let fixture: ComponentFixture<OportunidadeModalComponent>;
  let licitacoes: { detalharCompra: ReturnType<typeof vi.fn> };
  let dialogRef: { close: ReturnType<typeof vi.fn> };

  function montar(salva: OportunidadeSalvaResponse = SALVA) {
    TestBed.configureTestingModule({
      imports: [OportunidadeModalComponent],
      providers: [
        { provide: LicitacoesService, useValue: licitacoes },
        { provide: DialogRef, useValue: dialogRef },
        { provide: DIALOG_DATA, useValue: salva },
      ],
    });
    fixture = TestBed.createComponent(OportunidadeModalComponent);
    fixture.detectChanges();
  }

  beforeEach(() => {
    licitacoes = { detalharCompra: vi.fn(() => of(DETALHE)) };
    dialogRef = { close: vi.fn() };
  });

  function texto(): string {
    return fixture.debugElement.nativeElement.textContent;
  }

  it('desenha o mesmo card da busca a partir do snapshot salvo', () => {
    montar();

    expect(fixture.debugElement.query(By.css('.edital-card'))).not.toBeNull();
    expect(texto()).toContain('Aquisição de café e açúcar');
    expect(texto()).toContain('Café torrado e moído');
    expect(texto()).toContain('Salva por Gustavo');
  });

  it('o que muda com o tempo é consultado na origem ao abrir', () => {
    montar();

    expect(licitacoes.detalharCompra).toHaveBeenCalledWith('12345678000199', '2026', '42');
    // Documentos chegaram: a aba já conta 1.
    const abas = fixture.debugElement.queryAll(By.css('.aba'));
    expect(abas[1].nativeElement.textContent).toContain('1');
  });

  it('falha na consulta não derruba o modal — o card continua com o snapshot', () => {
    licitacoes.detalharCompra.mockReturnValue(throwError(() => new Error('falhou')));

    montar();

    expect(texto()).toContain('Aquisição de café e açúcar');
    // Selo CAPAG gravado ao salvar continua valendo.
    expect(fixture.debugElement.query(By.css('.selo-capag')).nativeElement.textContent).toContain(
      'CAPAG B',
    );
  });

  it('não oferece salvar de novo: a oportunidade já está na lista', () => {
    montar();

    expect(fixture.debugElement.query(By.css('.btn-salvar'))).toBeNull();
    expect(fixture.debugElement.query(By.css('.btn-salva'))).toBeNull();
  });

  it('oportunidade vencida avisa que não dá mais pra gerar proposta', () => {
    montar({
      ...SALVA,
      expirada: true,
      data_encerramento_proposta: '2026-08-01',
      itens: [{ ...ITEM, contratacao_data_encerramento_proposta: '2026-08-01' }],
    });

    expect(
      fixture.debugElement.query(By.css('.aviso-encerrada')).nativeElement.textContent,
    ).toContain('Não é mais possível gerar proposta');
  });

  it('fechar encerra o diálogo', () => {
    montar();

    fixture.debugElement.query(By.css('.modal-close')).nativeElement.click();

    expect(dialogRef.close).toHaveBeenCalled();
  });

  it('compra sem itens guardados (trazida pela Sentinela) abre sem quebrar', () => {
    montar({ ...SALVA, itens: [] });

    expect((fixture.nativeElement as HTMLElement).textContent).toContain(SALVA.orgao_nome);
  });
});
