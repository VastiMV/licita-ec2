import { ComponentFixture, TestBed } from '@angular/core/testing';

import { CartaoTorre } from '../../../contracts/licitacoes/torre.contracts';
import { COTADA, FARROUPILHA, PMDF } from '../torre.testing';
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

  it('como no protótipo: etapa, UASG, órgão, compra com o item, posição e conta', () => {
    const el = montar(FARROUPILHA);

    expect(el.querySelector('.etapa')?.textContent).toContain('Aguardando julgamento');
    expect(el.querySelector('.etapa')?.getAttribute('data-estagio')).toBe('disputar');
    expect(el.querySelector('.local')?.textContent).toContain('UASG 158127');
    expect(el.querySelector('.compra')?.textContent).toBe('Pregão 61/2026 · item 22');
    expect(el.querySelector('.linha')?.textContent).toBe(
      '1º lugar · 20 × R$\u00a011.999,00 = R$\u00a0239.980,00',
    );
  });

  it('a trilha mostra a etapa de agora e as que faltam', () => {
    const passos = Array.from(montar(FARROUPILHA).querySelectorAll('.trilha > span'))
      .map((s) => s.textContent?.trim())
      .filter((t) => t !== '›');

    expect(passos).toEqual([
      '● Aguardando julgamento',
      'Aceita e habilitada',
      'Habilitada (aguardando adjudicação)',
    ]);
  });

  it('etiqueta de alerta pinta o cartão e aparece com o texto', () => {
    const el = montar(FARROUPILHA);

    expect(el.querySelector('.cartao')?.getAttribute('data-nivel')).toBe('alerta');
    expect(el.querySelector('.etiqueta')?.textContent).toContain('convocação em andamento');
  });

  it('com itens perdendo: o item à frente na compra e quantos estão perdendo', () => {
    const el = montar(PMDF);

    expect(el.querySelector('.compra')?.textContent).toBe('Pregão 56/2026 · item 22');
    expect(el.querySelector('.linha')?.textContent).toBe('1 item · R$\u00a015.500,00');
    expect(el.querySelector('.perdendo')?.textContent).toBe('👎 2 perdendo');
  });

  it('dentro da coluna da etapa, sem a pílula repetida', () => {
    TestBed.configureTestingModule({ imports: [TorreCartaoComponent] });
    fixture = TestBed.createComponent(TorreCartaoComponent);
    fixture.componentRef.setInput('cartao', FARROUPILHA);
    fixture.componentRef.setInput('semEtapa', true);
    fixture.detectChanges();

    expect((fixture.nativeElement as HTMLElement).querySelector('.etapa')).toBeNull();
  });

  it('em Preparar mostra o prazo da proposta como etiqueta', () => {
    const el = montar(COTADA);

    expect(el.querySelector('.etiqueta')?.textContent).toContain('Proposta até 17/11');
  });

  it('clicar emite abrir com o cartão', () => {
    montar(PMDF);
    const emitidos: CartaoTorre[] = [];
    fixture.componentInstance.abrir.subscribe((c) => emitidos.push(c));

    (fixture.nativeElement.querySelector('.cartao-abrir') as HTMLButtonElement).click();

    expect(emitidos).toEqual([PMDF]);
  });

  it('lixeira em Preparar e Disputar, emitindo descartar', () => {
    const el = montar(FARROUPILHA);
    const emitidos: CartaoTorre[] = [];
    fixture.componentInstance.descartar.subscribe((c) => emitidos.push(c));

    const lixeira = el.querySelector('.lixeira') as HTMLButtonElement;
    expect(lixeira.getAttribute('aria-label')).toBe('Descartar Pregão 61/2026');
    lixeira.click();

    expect(emitidos).toEqual([FARROUPILHA]);
  });

  it('sem lixeira em Contratar (ali ele já ganhou)', () => {
    const el = montar({ ...FARROUPILHA, estagio: 'contratar', etapa: 'homologado' });

    expect(el.querySelector('.lixeira')).toBeNull();
  });
});
