import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';

import { AuthService } from '../../core/auth/auth.service';
import { torre } from '../../pages/torre/torre.testing';
import { TorreService } from '../../services/licitacoes/torre.service';
import { BrandComponent } from '../brand/brand.component';
import { NavGroupComponent } from '../nav-group/nav-group.component';
import { NavItemComponent } from '../nav-item/nav-item.component';
import { SidebarStateService } from './sidebar-state.service';
import { SidebarComponent } from './sidebar.component';

describe('SidebarComponent', () => {
  let fixture: ComponentFixture<SidebarComponent>;
  let state: SidebarStateService;
  const ehSuperusuario = signal(false);
  let torreService: { torre: ReturnType<typeof vi.fn> };

  beforeEach(() => {
    ehSuperusuario.set(false);
    torreService = { torre: vi.fn(() => of(torre())) };
    TestBed.configureTestingModule({
      imports: [SidebarComponent],
      // Rota curinga: o teste clica num link de verdade, e sem rota casada o
      // Router rejeita a navegação depois que o teste já terminou.
      providers: [
        provideRouter([{ path: '**', children: [] }]),
        // Só `ehSuperusuario` interessa aqui, e como signal — o menu reage à
        // troca sem remontar o componente.
        { provide: AuthService, useValue: { ehSuperusuario } },
        { provide: TorreService, useValue: torreService },
      ],
    });
    fixture = TestBed.createComponent(SidebarComponent);
    state = TestBed.inject(SidebarStateService);
    fixture.detectChanges();
  });

  const SECOES = ['Preparar', 'Disputar', 'Contratar', 'Receber', 'Cadastros'];

  const secoes = () =>
    fixture.debugElement
      .queryAll(By.css('.secao'))
      .map((secao) => (secao.nativeElement as HTMLElement).textContent?.trim());

  const rotulosDosGrupos = () =>
    fixture.debugElement
      .queryAll(By.directive(NavGroupComponent))
      .map((grupo) => (grupo.componentInstance as NavGroupComponent).label());

  const itens = () =>
    fixture.debugElement
      .queryAll(By.directive(NavItemComponent))
      .map((item) => item.componentInstance as NavItemComponent);

  const item = (rotulo: string) => itens().find((i) => i.label() === rotulo);

  it('mostra a marca, Buscar em destaque, a Torre e os 4 estágios sempre abertos', () => {
    expect(fixture.debugElement.query(By.directive(BrandComponent))).toBeTruthy();
    expect(secoes()).toEqual(SECOES);
    expect(rotulosDosGrupos()).toEqual([]);
    expect(item('Buscar oportunidades')?.destaque()).toBe(true);

    expect(itens().map((i) => i.label())).toEqual([
      'Buscar oportunidades',
      'Torre de Controle',
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

  it('o título de cada estágio leva ao estágio aberto', () => {
    const links = fixture.debugElement
      .queryAll(By.css('a.secao'))
      .map((a) => (a.nativeElement as HTMLAnchorElement).getAttribute('href'));

    expect(links).toEqual([
      '/torre/estagio/preparar',
      '/torre/estagio/disputar',
      '/torre/estagio/contratar',
      '/torre/estagio/receber',
    ]);
  });

  it('cada etapa mostra quantas licitações estão nela, e as saídas também', () => {
    expect(item('Cotação')?.contagem()).toBe(1);
    expect(item('Aguardando julgamento')?.contagem()).toBe(1);
    expect(item('Disputa')?.contagem()).toBe(0);
    expect(item('Encerradas')?.contagem()).toBe(3);
    expect(item('Descartadas')?.contagem()).toBe(8);
    expect(item('Empresas')?.contagem()).toBeNull();

    const numeros = fixture.debugElement
      .queryAll(By.css('.n:not(.zero)'))
      .map((n) => (n.nativeElement as HTMLElement).textContent?.trim());
    expect(numeros).toEqual(['1', '1', '1', '3', '8']);
  });

  it('sem a Torre (erro), o menu funciona, só sem os números', () => {
    torreService.torre.mockReturnValue(throwError(() => new Error('fora do ar')));
    fixture = TestBed.createComponent(SidebarComponent);
    fixture.detectChanges();

    expect(itens().length).toBe(21);
  });

  it('Configurações só aparece para administrador', () => {
    // Cortesia, não segurança: quem barra é o backend (403). O menu só não
    // oferece o que a pessoa não pode usar.
    expect(rotulosDosGrupos()).toEqual([]);

    ehSuperusuario.set(true);
    fixture.detectChanges();

    expect(rotulosDosGrupos()).toEqual(['Configurações']);
  });

  it('cada etapa aponta para a sua lista; Oportunidade e Cotação para as que já existiam', () => {
    const rotas = itens().map((i) => i.path());

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

  it('a Torre de Controle só acende no endereço exato (as etapas começam com /torre)', () => {
    expect(item('Torre de Controle')?.exato()).toBe(true);
    expect(item('Disputa')?.exato()).toBe(false);
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
    ehSuperusuario.set(true);
    state.mobileOpen.set(true);
    fixture.detectChanges();

    fixture.debugElement.query(By.css('.grupo-cabecalho')).nativeElement.click();

    expect(state.mobileOpen()).toBe(true);
  });
});
