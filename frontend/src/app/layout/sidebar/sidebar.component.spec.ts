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

  const GRUPOS = ['Torre de Controle', 'Preparar', 'Disputar', 'Contratar', 'Receber', 'Cadastros'];

  const rotulosDosGrupos = () =>
    fixture.debugElement
      .queryAll(By.directive(NavGroupComponent))
      .map((grupo) => (grupo.componentInstance as NavGroupComponent).label());

  const itens = () =>
    fixture.debugElement
      .queryAll(By.directive(NavItemComponent))
      .map((item) => item.componentInstance as NavItemComponent);

  it('mostra a marca, Buscar no topo e a Torre com os 4 estágios e as 13 etapas', () => {
    expect(fixture.debugElement.query(By.directive(BrandComponent))).toBeTruthy();
    expect(rotulosDosGrupos()).toEqual(GRUPOS);

    expect(itens().map((item) => item.label())).toEqual([
      'Buscar oportunidades',
      'Visão geral',
      'Oportunidade',
      'Cotação',
      'Cadastro de proposta',
      'Disputa',
      'Aguardando julgamento',
      'Julgado e habilitado',
      'Aguardando adjudicação',
      'Homologado',
      'Contrato',
      'Empenho / OF',
      'Entrega',
      'Liquidado',
      'Recebido',
      'Encerradas',
      'Descartadas',
      'Propostas (PDF)',
      'Empresas',
      'Fornecedores',
      'Produtos',
    ]);
  });

  it('Configurações só aparece para administrador', () => {
    // Cortesia, não segurança: quem barra é o backend (403). O menu só não
    // oferece o que a pessoa não pode usar.
    expect(rotulosDosGrupos()).toEqual(GRUPOS);

    ehSuperusuario.set(true);
    fixture.detectChanges();

    expect(rotulosDosGrupos()).toEqual([...GRUPOS, 'Configurações']);
  });

  it('cada etapa aponta para a sua lista; Oportunidade e Cotação para as que já existiam', () => {
    const rotas = itens().map((item) => item.path());

    expect(rotas.slice(0, 18)).toEqual([
      '/oportunidades/buscar',
      '/torre',
      '/oportunidades/salvas',
      '/ciclo/cotador',
      '/torre/etapa/cadastro_proposta',
      '/torre/etapa/disputa',
      '/torre/etapa/aguardando_julgamento',
      '/torre/etapa/julgado_habilitado',
      '/torre/etapa/aguardando_adjudicacao',
      '/torre/etapa/homologado',
      '/torre/etapa/contrato',
      '/torre/etapa/empenho',
      '/torre/etapa/entrega',
      '/torre/etapa/liquidado',
      '/torre/etapa/recebido',
      '/ciclo/encerradas',
      '/ciclo/descartadas',
      '/ciclo/propostas',
    ]);
  });

  it('a Visão geral só acende no endereço exato (as etapas começam com /torre)', () => {
    const visaoGeral = itens().find((item) => item.label() === 'Visão geral');
    const etapa = itens().find((item) => item.label() === 'Disputa');

    expect(visaoGeral?.exato()).toBe(true);
    expect(etapa?.exato()).toBe(false);
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
