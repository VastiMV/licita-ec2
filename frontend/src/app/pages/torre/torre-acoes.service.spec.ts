import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';

import { TorreService } from '../../services/licitacoes/torre.service';
import { ModalService } from '../../shared/overlay/modal.service';
import { ToastService } from '../../shared/ui/toast/toast.service';
import { CotadorModalComponent } from '../oportunidades/cotador-modal/cotador-modal.component';
import { OportunidadeModalComponent } from '../oportunidades/salvas/oportunidade-modal/oportunidade-modal.component';
import { TorreAcoesService, abrirNoCompras } from './torre-acoes.service';
import { COTADA, FARROUPILHA } from './torre.testing';

describe('TorreAcoesService', () => {
  function servico(resultado: unknown = undefined) {
    const modal = { abrir: vi.fn(() => of(resultado)) };
    TestBed.configureTestingModule({ providers: [{ provide: ModalService, useValue: modal }] });
    return { acoes: TestBed.inject(TorreAcoesService), modal };
  }

  it('cartão com cotação abre o Cotador e pede recarga', () => {
    const { acoes, modal } = servico();
    const recargas: boolean[] = [];

    acoes.abrir(COTADA).subscribe((r) => recargas.push(r));

    expect(modal.abrir).toHaveBeenCalledWith(
      CotadorModalComponent,
      expect.objectContaining({ oportunidadeId: 7 }),
    );
    expect(recargas).toEqual([true]);
  });

  it('oportunidade abre o visualizador; "cotar" segue para o Cotador', () => {
    const { acoes, modal } = servico('cotar');
    const oportunidade = { ...COTADA, etapa: 'oportunidade' as const, cotacao_id: null };

    acoes.abrir(oportunidade).subscribe();

    expect(modal.abrir).toHaveBeenNthCalledWith(1, OportunidadeModalComponent, oportunidade.salva);
    expect(modal.abrir).toHaveBeenNthCalledWith(2, CotadorModalComponent, expect.anything());
  });

  it('cadastro de proposta sem cotação também abre o visualizador (dá para cotar)', () => {
    // Dispensa 27/2026 (10/11/2026): a Sentinela pôs em Cadastro de proposta
    // porque ele já aceitou no Compras.gov; o clique abria o Compras.gov e não
    // havia como chegar ao Cotador pela Torre.
    const { acoes, modal } = servico('cotar');
    const semCotacao = { ...COTADA, etapa: 'cadastro_proposta' as const, cotacao_id: null };

    acoes.abrir(semCotacao).subscribe();

    expect(modal.abrir).toHaveBeenNthCalledWith(1, OportunidadeModalComponent, semCotacao.salva);
    expect(modal.abrir).toHaveBeenNthCalledWith(2, CotadorModalComponent, expect.anything());
  });

  it('depois de Preparar, abre a compra no Compras.gov sem recarregar', () => {
    const { acoes, modal } = servico();
    const abrirJanela = vi.spyOn(window, 'open').mockReturnValue(null);
    const recargas: boolean[] = [];

    acoes.abrir(FARROUPILHA).subscribe((r) => recargas.push(r));

    expect(modal.abrir).not.toHaveBeenCalled();
    expect(abrirJanela).toHaveBeenCalledWith(FARROUPILHA.link_plataforma, '_blank', 'noopener');
    expect(recargas).toEqual([false]);
    abrirJanela.mockRestore();
  });

  describe('lixeira', () => {
    function comLixeira(confirmou: boolean) {
      const modal = { abrir: vi.fn(), confirmar: vi.fn(() => of(confirmou)) };
      const torre = {
        resumoDoDescarte: vi.fn(() =>
          of({
            pergunta:
              'Você tem preço cadastrado no item 22 (R$ 11.999,00, 1º lugar). Deseja prosseguir?',
            tira_favorito: true,
          }),
        ),
        descartar: vi.fn(() => of({ descricao: 'ok' })),
      };
      const toast = { sucesso: vi.fn(), erro: vi.fn() };
      TestBed.configureTestingModule({
        providers: [
          { provide: ModalService, useValue: modal },
          { provide: TorreService, useValue: torre },
          { provide: ToastService, useValue: toast },
        ],
      });
      return { acoes: TestBed.inject(TorreAcoesService), modal, torre, toast };
    }

    it('pergunta mostrando o preço lançado e, confirmado, descarta e pede recarga', () => {
      const { acoes, modal, torre, toast } = comLixeira(true);
      const recargas: boolean[] = [];

      acoes.descartar(FARROUPILHA).subscribe((r) => recargas.push(r));

      expect(modal.confirmar).toHaveBeenCalledWith(
        expect.objectContaining({
          titulo: 'Descartar Pregão 61/2026?',
          mensagem: expect.stringContaining('item 22'),
          confirmarLabel: 'Descartar',
        }),
      );
      expect(modal.confirmar).toHaveBeenCalledWith(
        expect.objectContaining({
          mensagem: expect.stringContaining('a Sentinela tira o favorito'),
        }),
      );
      expect(torre.descartar).toHaveBeenCalledWith(FARROUPILHA.id);
      expect(toast.sucesso).toHaveBeenCalled();
      expect(recargas).toEqual([true]);
    });

    it('cancelou: não descarta nem recarrega', () => {
      const { acoes, torre } = comLixeira(false);
      const recargas: boolean[] = [];

      acoes.descartar(FARROUPILHA).subscribe((r) => recargas.push(r));

      expect(torre.descartar).not.toHaveBeenCalled();
      expect(recargas).toEqual([false]);
    });
  });

  describe('abrir no Compras.gov', () => {
    afterEach(() => delete document.documentElement.dataset['sentinela']);

    it('com a Sentinela no Chrome, pede a ela (aba logada), sem abrir aba vazia', () => {
      document.documentElement.dataset['sentinela'] = '0.1.3';
      const postMessage = vi.spyOn(window, 'postMessage').mockImplementation(() => undefined);
      const open = vi.spyOn(window, 'open').mockImplementation(() => null);

      abrirNoCompras('https://cnetmobile.estaleiro.serpro.gov.br/x');

      expect(postMessage).toHaveBeenCalledWith(
        {
          licita: true,
          tipo: 'abrir_no_compras',
          url: 'https://cnetmobile.estaleiro.serpro.gov.br/x',
        },
        location.origin,
      );
      expect(open).not.toHaveBeenCalled();
    });

    it('sem Sentinela, abre uma aba nova como antes', () => {
      const open = vi.spyOn(window, 'open').mockImplementation(() => null);

      abrirNoCompras('https://cnetmobile.estaleiro.serpro.gov.br/x');

      expect(open).toHaveBeenCalledWith(
        'https://cnetmobile.estaleiro.serpro.gov.br/x',
        '_blank',
        'noopener',
      );
    });
  });
});
