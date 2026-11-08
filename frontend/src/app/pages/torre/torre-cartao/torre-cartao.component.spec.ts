import { ComponentFixture, TestBed } from '@angular/core/testing';

import { CartaoTorre } from '../../../contracts/licitacoes/torre.contracts';
import { FARROUPILHA, PMDF } from '../torre.testing';
import { TorreCartaoComponent } from './torre-cartao.component';

describe('TorreCartaoComponent', () => {
  let fixture: ComponentFixture<TorreCartaoComponent>;

  function montar(cartao: CartaoTorre): HTMLElement {
    TestBed.configureTestingModule({ imports: [TorreCartaoComponent] });
    fixture = TestBed.createComponent(TorreCartaoComponent);
    fixture.componentRef.setInput('cartao', cartao);
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  it('mostra a etapa, o órgão, o item com a posição e o valor', () => {
    const el = montar(FARROUPILHA);

    expect(el.querySelector('.etapa')?.textContent).toContain('Aguardando julgamento');
    expect(el.querySelector('.etapa')?.getAttribute('data-estagio')).toBe('disputar');
    expect(el.querySelector('.local')?.textContent).toContain('UASG 158127');
    expect(el.querySelector('.itens li')?.textContent).toContain('Item 22 · 1º');
    expect(el.querySelector('.valor')?.textContent).toContain('R$\u00a0239.980,00');
  });

  it('etiqueta de alerta pinta o cartão e aparece com o texto', () => {
    const el = montar(FARROUPILHA);

    expect(el.querySelector('.cartao')?.getAttribute('data-nivel')).toBe('alerta');
    expect(el.querySelector('.etiqueta')?.textContent).toContain('convocação em andamento');
  });

  it('item perdendo fica em cinza', () => {
    const el = montar(PMDF);

    const linhas = Array.from(el.querySelectorAll('.itens li'));
    expect(linhas[0].classList.contains('perdendo')).toBe(true);
    expect(linhas[2].classList.contains('perdendo')).toBe(false);
  });

  it('tem o link para a compra no Compras.gov, em outra aba', () => {
    const link = montar(FARROUPILHA).querySelector('a.no-compras') as HTMLAnchorElement;

    expect(link.href).toContain('acompanhamento-compra?compra=15812705000612026');
    expect(link.target).toBe('_blank');
  });

  it('clicar emite abrir com o cartão', () => {
    montar(PMDF);
    const emitidos: CartaoTorre[] = [];
    fixture.componentInstance.abrir.subscribe((c) => emitidos.push(c));

    (fixture.nativeElement.querySelector('.cartao-abrir') as HTMLButtonElement).click();

    expect(emitidos).toEqual([PMDF]);
  });
});
