import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { provideRouter } from '@angular/router';

import { AuthService } from '../../core/auth/auth.service';
import { BrandComponent } from '../brand/brand.component';
import { NavGroupComponent } from '../nav-group/nav-group.component';
import { NavItemComponent } from '../nav-item/nav-item.component';
import { SidebarStateService } from './sidebar-state.service';
import { SidebarComponent } from './sidebar.component';

describe('SidebarComponent', () => {
  let fixture: ComponentFixture<SidebarComponent>;
  let state: SidebarStateService;
  const ehSuperusuario = signal(false);

  beforeEach(() => {
    ehSuperusuario.set(false);
    TestBed.configureTestingModule({
      imports: [SidebarComponent],
      // Rota curinga: o teste clica num link de verdade, e sem rota casada o
      // Router rejeita a navegação depois que o teste já terminou.
      providers: [
        provideRouter([{ path: '**', children: [] }]),
        // Só `ehSuperusuario` interessa aqui, e como signal — o menu reage à
        // troca sem remontar o componente.
        { provide: AuthService, useValue: { ehSuperusuario } },
      ],
    });
    fixture = TestBed.createComponent(SidebarComponent);
    state = TestBed.inject(SidebarStateService);
    fixture.detectChanges();
  });

  it('mostra a marca e o Ciclo de Licitação com Oportunidades e as etapas dentro', () => {
    expect(fixture.debugElement.query(By.directive(BrandComponent))).toBeTruthy();

    const grupos = fixture.debugElement
      .queryAll(By.directive(NavGroupComponent))
      .map((grupo) => (grupo.componentInstance as NavGroupComponent).label());
    expect(grupos).toEqual(['Ciclo de Licitação', 'Oportunidades', 'Cadastros']);

    // "Visão Geral" é o quadro; Oportunidades é subgrupo, com "Buscar"
    // antes de "Salvas" (a busca é a tela inicial do app).

    const items = fixture.debugElement.queryAll(By.directive(NavItemComponent));
    const labels = items.map((item) => (item.componentInstance as NavItemComponent).label());
    expect(labels).toEqual([
      'Visão Geral',
      'Buscar',
      'Salvas',
      'Cotador',
      'Propostas',
      'Disputas',
      'Empenhos',
      'Encerradas',
      'Descartadas',
      'Empresas',
      'Fornecedores',
      'Produtos',
    ]);
  });

  it('Configurações só aparece para administrador', () => {
    // Cortesia, não segurança: quem barra é o backend (403). O menu só não
    // oferece o que a pessoa não pode usar.
    const rotulos = () =>
      fixture.debugElement
        .queryAll(By.directive(NavGroupComponent))
        .map((grupo) => (grupo.componentInstance as NavGroupComponent).label());

    expect(rotulos()).toEqual(['Ciclo de Licitação', 'Oportunidades', 'Cadastros']);

    ehSuperusuario.set(true);
    fixture.detectChanges();

    expect(rotulos()).toEqual([
      'Ciclo de Licitação',
      'Oportunidades',
      'Cadastros',
      'Configurações',
    ]);
  });

  it('cada item do Ciclo aponta para a sua rota', () => {
    const rotas = fixture.debugElement
      .queryAll(By.directive(NavItemComponent))
      .map((item) => (item.componentInstance as NavItemComponent).path());

    expect(rotas.slice(0, 9)).toEqual([
      '/ciclo/visao-geral',
      '/oportunidades/buscar',
      '/oportunidades/salvas',
      '/ciclo/cotador',
      '/ciclo/propostas',
      '/ciclo/disputas',
      '/ciclo/empenhos',
      '/ciclo/encerradas',
      '/ciclo/descartadas',
    ]);
  });

  it('o botão de colapso alterna SidebarStateService.collapsed', () => {
    const botao = fixture.debugElement.query(By.css('.collapse-toggle'));

    botao.nativeElement.click();
    expect(state.collapsed()).toBe(true);

    botao.nativeElement.click();
    expect(state.collapsed()).toBe(false);
  });

  it('aplica a classe collapsed no aside quando recolhido', () => {
    state.collapsed.set(true);
    fixture.detectChanges();

    const aside = fixture.debugElement.query(By.css('aside.sidebar'));
    expect(aside.classes['collapsed']).toBe(true);
  });

  it('clicar num item de menu fecha o menu mobile', () => {
    state.mobileOpen.set(true);
    fixture.detectChanges();

    fixture.debugElement.query(By.css('nav a')).nativeElement.click();
    expect(state.mobileOpen()).toBe(false);
  });

  it('abrir/fechar um grupo não fecha o menu mobile', () => {
    state.mobileOpen.set(true);
    fixture.detectChanges();

    fixture.debugElement.query(By.css('.grupo-cabecalho')).nativeElement.click();

    expect(state.mobileOpen()).toBe(true);
  });
});
