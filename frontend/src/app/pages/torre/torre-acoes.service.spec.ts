import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';

import { ModalService } from '../../shared/overlay/modal.service';
import { CotadorModalComponent } from '../oportunidades/cotador-modal/cotador-modal.component';
import { OportunidadeModalComponent } from '../oportunidades/salvas/oportunidade-modal/oportunidade-modal.component';
import { TorreAcoesService } from './torre-acoes.service';
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
});
