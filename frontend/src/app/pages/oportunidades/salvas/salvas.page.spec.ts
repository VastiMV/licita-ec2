import { ComponentFixture, TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { of, throwError } from 'rxjs';

import { OportunidadeSalvaResponse } from '../../../contracts/licitacoes/oportunidade-salva.contracts';
import { OportunidadesSalvasService } from '../../../services/licitacoes/oportunidades-salvas.service';
import { ModalService } from '../../../shared/overlay/modal.service';
import { MenuComponent } from '../../../shared/ui/menu/menu.component';
import { ToastService } from '../../../shared/ui/toast/toast.service';
import { CotadorModalComponent } from '../cotador-modal/cotador-modal.component';
import { OportunidadeModalComponent } from './oportunidade-modal/oportunidade-modal.component';
import { SalvasPage } from './salvas.page';

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
  data_encerramento_proposta: '2026-09-10',
  valor_total_estimado: 1850,
  plataforma_id: 'compras_gov',
  plataforma_nome: '',
  link_plataforma: 'https://compras.gov.br/compra/1',
  link_pncp: 'https://pncp.gov.br/app/editais/12345678000199/2026/42',
  capag: null,
  itens: [],
  expirada: false,
  salva_por: 'Gustavo',
  criada_em: '2026-08-25T12:00:00Z',
};

const VENCIDA: OportunidadeSalvaResponse = {
  ...SALVA,
  id: 2,
  chave: '12345678000199-2026-43',
  sequencial_compra: '43',
  uasg: '110161',
  objeto: 'Serviço de limpeza predial',
  municipio: 'São Miguel do Oeste dos Campos Gerais',
  uf: 'SC',
  data_encerramento_proposta: '2026-08-01',
  expirada: true,
};

function pagina(results: OportunidadeSalvaResponse[]) {
  return { count: results.length, next: null, previous: null, results };
}

describe('SalvasPage', () => {
  let fixture: ComponentFixture<SalvasPage>;
  let service: {
    listar: ReturnType<typeof vi.fn>;
    remover: ReturnType<typeof vi.fn>;
  };
  let modal: { confirmar: ReturnType<typeof vi.fn>; abrir: ReturnType<typeof vi.fn> };
  let toast: {
    sucesso: ReturnType<typeof vi.fn>;
    erro: ReturnType<typeof vi.fn>;
    alerta: ReturnType<typeof vi.fn>;
  };

  beforeEach(() => {
    service = {
      listar: vi.fn(() => of(pagina([SALVA, VENCIDA]))),
      remover: vi.fn(() => of(undefined)),
    };
    modal = { confirmar: vi.fn(() => of(true)), abrir: vi.fn(() => of(undefined)) };
    toast = { sucesso: vi.fn(), erro: vi.fn(), alerta: vi.fn() };

    TestBed.configureTestingModule({
      imports: [SalvasPage],
      providers: [
        { provide: OportunidadesSalvasService, useValue: service },
        { provide: ModalService, useValue: modal },
        { provide: ToastService, useValue: toast },
      ],
    });
    fixture = TestBed.createComponent(SalvasPage);
    fixture.detectChanges();
  });

  function linhas() {
    return fixture.debugElement.queryAll(By.css('tbody tr'));
  }

  /** As ações vivem num menu; abrir o menu monta o painel num overlay do
   * CDK, fora da árvore do componente — por isso a busca é no document. */
  function abrirMenuDaLinha(indice: number): HTMLButtonElement[] {
    linhas()[indice].query(By.css('app-menu .gatilho')).nativeElement.click();
    fixture.detectChanges();
    return Array.from(document.querySelectorAll<HTMLButtonElement>('.menu-item'));
  }

  function clicarAcao(indice: number, rotulo: string): void {
    const item = abrirMenuDaLinha(indice).find((botao) => botao.textContent?.includes(rotulo));
    item!.click();
    fixture.detectChanges();
  }

  it('carrega a lista ao abrir, o prazo que vence primeiro no topo', () => {
    expect(service.listar).toHaveBeenCalledWith({
      page: 1,
      page_size: 10,
      ordering: 'prazo',
      busca: '',
    });
    expect(linhas()).toHaveLength(2);
  });

  it('mostra os campos da tabela já formatados', () => {
    const celulas = linhas()[0]
      .queryAll(By.css('td'))
      .map((td) => td.nativeElement.textContent.trim());

    // O nome da unidade vem embaixo da UASG.
    expect(celulas[0]).toBe('925997Prefeitura de Campinas');
    expect(celulas[1]).toBe('Aquisição de café e açúcar');
    expect(celulas[2]).toBe('Pregão Eletrônico');
    expect(celulas[3]).toBe('Campinas / SP');
    expect(celulas[4]).toBe('20/08/2026');
    expect(celulas[5]).toBe('10/09/2026');
    expect(celulas[6]).toBe('R$ 1.850,00');
  });

  it('o objeto tem coluna própria, cortada em duas linhas, com o texto inteiro na dica', () => {
    const objeto = linhas()[0].queryAll(By.css('td'))[1].nativeElement as HTMLElement;

    expect(objeto.getAttribute('title')).toBe('Aquisição de café e açúcar');
    expect(objeto.querySelector('.celula-conteudo.limitada')).toBeTruthy();
  });

  it('cidade longa é cortada com reticências, sem perder a UF nem quebrar linha', () => {
    const cidade = linhas()[1].queryAll(By.css('td'))[3].nativeElement;

    expect(cidade.textContent.trim()).toBe('São Miguel do Oeste dos… / SC');
    expect(cidade.className).toContain('uma-linha');
    // O nome inteiro fica na dica.
    expect(cidade.getAttribute('title')).toBe('São Miguel do Oeste dos Campos Gerais / SC');
  });

  it('as ações ficam num menu por linha, não como botões soltos', () => {
    expect(fixture.debugElement.queryAll(By.directive(MenuComponent))).toHaveLength(2);

    const opcoes = abrirMenuDaLinha(0).map((botao) => botao.textContent?.trim());
    expect(opcoes).toEqual(['Visualizar', 'Abrir cotação', 'Excluir']);
  });

  it('visualizar abre o modal com a oportunidade salva', () => {
    clicarAcao(0, 'Visualizar');

    expect(modal.abrir).toHaveBeenCalledWith(OportunidadeModalComponent, SALVA);
  });

  it('"Abrir cotação" abre o Cotador pelo id da oportunidade, não pelo da cotação', () => {
    clicarAcao(0, 'Abrir cotação');

    expect(modal.abrir).toHaveBeenCalledWith(
      CotadorModalComponent,
      expect.objectContaining({ oportunidadeId: SALVA.id }),
    );
  });

  it('o Cotador de uma salva recebe os itens do snapshot, para abrir sem rede', () => {
    clicarAcao(0, 'Abrir cotação');

    const dados = modal.abrir.mock.calls.at(-1)![1] as { itens: unknown };
    expect(dados.itens).toBe(SALVA.itens);
  });

  it('excluir avisa que a ação não pode ser desfeita e só exclui se confirmado', () => {
    clicarAcao(0, 'Excluir');

    expect(modal.confirmar).toHaveBeenCalledWith(
      expect.objectContaining({ mensagem: expect.stringContaining('não poderá ser desfeita') }),
    );
    expect(service.remover).toHaveBeenCalledWith(1);
    expect(toast.sucesso).toHaveBeenCalled();
    // Recarrega a lista depois de excluir.
    expect(service.listar).toHaveBeenCalledTimes(2);
  });

  it('excluir cancelado não chama o serviço', () => {
    modal.confirmar.mockReturnValue(of(false));

    clicarAcao(0, 'Excluir');

    expect(service.remover).not.toHaveBeenCalled();
  });

  it('falha ao excluir avisa e não some com a linha', () => {
    service.remover.mockReturnValue(throwError(() => new Error('falhou')));

    clicarAcao(0, 'Excluir');

    expect(toast.erro).toHaveBeenCalled();
    expect(linhas()).toHaveLength(2);
  });

  it('ordenar por uma coluna refaz a consulta com o `ordering` do backend', () => {
    fixture.debugElement.queryAll(By.css('thead th .ordenar'))[0].nativeElement.click();

    expect(service.listar).toHaveBeenLastCalledWith(
      expect.objectContaining({ ordering: 'uasg', page: 1 }),
    );
  });

  it('erro ao carregar mostra a mensagem e esvazia a tabela', () => {
    service.listar.mockReturnValue(throwError(() => new Error('falhou')));
    fixture = TestBed.createComponent(SalvasPage);
    fixture.detectChanges();

    expect(fixture.debugElement.query(By.css('.erro')).nativeElement.textContent).toContain(
      'Não foi possível carregar',
    );
    expect(linhas()).toHaveLength(1); // a linha de "nenhum registro"
  });
});
