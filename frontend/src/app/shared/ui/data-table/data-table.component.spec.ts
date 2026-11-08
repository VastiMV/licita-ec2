import { Component, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';

import { DataTableComponent } from './data-table.component';
import { ColunaTabela, EstadoTabela, estadoInicialTabela } from './data-table.model';
import { TabelaAcoesDirective } from './tabela-acoes.directive';

interface Linha {
  readonly id: number;
  readonly nome: string;
  readonly valor: number;
  readonly vencida: boolean;
}

const LINHAS: Linha[] = [
  { id: 1, nome: 'Café torrado', valor: 1850, vencida: true },
  { id: 2, nome: 'Areia lavada', valor: 320, vencida: false },
];

const COLUNAS: ColunaTabela<Linha>[] = [
  { chave: 'nome', titulo: 'Descrição', valor: (l) => l.nome, limiteLinhas: 2 },
  {
    chave: 'valor',
    titulo: 'Valor',
    valor: (l) => `R$ ${l.valor}`,
    numerica: true,
    tom: (l) => (l.vencida ? 'perigo' : null),
  },
  { chave: 'fixa', titulo: 'Fixa', valor: () => '—', ordenavel: false },
];

@Component({
  imports: [DataTableComponent, TabelaAcoesDirective],
  template: `<app-data-table
    [colunas]="colunas"
    [linhas]="linhas()"
    [total]="total()"
    [estado]="estado()"
    [carregando]="carregando()"
    [chaveDe]="chaveDe"
    [destacada]="destacada"
    mensagemVazia="Nada aqui."
    [linhaClicavel]="true"
    (estadoMudou)="aoMudar($event)"
    (linhaClicada)="aberta.set($event.id)"
  >
    <ng-template appTabelaAcoes let-linha>
      <button type="button" class="acao-teste" (click)="acionada.set(linha.id)">Ação</button>
    </ng-template>
  </app-data-table>`,
})
class HostComponent {
  readonly colunas = COLUNAS;
  readonly linhas = signal<readonly Linha[]>(LINHAS);
  readonly total = signal(2);
  readonly carregando = signal(false);
  readonly estado = signal<EstadoTabela>(estadoInicialTabela());
  readonly ultimoEstado = signal<EstadoTabela | null>(null);
  readonly acionada = signal<number | null>(null);
  readonly aberta = signal<number | null>(null);

  readonly chaveDe = (linha: Linha) => linha.id;
  readonly destacada = (linha: Linha) => linha.vencida;

  // A página é dona do estado: aplica o que a tabela pediu e recarregaria.
  aoMudar(estado: EstadoTabela): void {
    this.ultimoEstado.set(estado);
    this.estado.set(estado);
  }
}

describe('DataTableComponent', () => {
  let fixture: ComponentFixture<HostComponent>;
  let host: HostComponent;

  beforeEach(() => {
    vi.useFakeTimers();
    TestBed.configureTestingModule({ imports: [HostComponent] });
    fixture = TestBed.createComponent(HostComponent);
    host = fixture.componentInstance;
    fixture.detectChanges();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  function celulas(): string[] {
    return fixture.debugElement
      .queryAll(By.css('tbody td'))
      .map((td) => td.nativeElement.textContent.trim());
  }

  it('desenha cabeçalho e células a partir das colunas', () => {
    const titulos = fixture.debugElement
      .queryAll(By.css('thead th'))
      .map((th) => th.nativeElement.textContent.trim());

    expect(titulos).toEqual(['Descrição', 'Valor', 'Fixa', 'Ações']);
    expect(celulas()).toContain('Café torrado');
    expect(celulas()).toContain('R$ 1850');
  });

  it('cada célula carrega o rótulo da coluna (é o que vira lista em tela estreita)', () => {
    const primeira = fixture.debugElement.query(By.css('tbody td'));

    expect(primeira.nativeElement.getAttribute('data-rotulo')).toBe('Descrição');
  });

  it('clicar num cabeçalho ordena por ele; clicar de novo inverte', () => {
    const cabecalhoNome = fixture.debugElement.queryAll(By.css('thead th .ordenar'))[0];

    cabecalhoNome.nativeElement.click();
    expect(host.ultimoEstado()).toMatchObject({ ordenarPor: 'nome', direcao: 'asc', pagina: 1 });

    fixture.detectChanges();
    cabecalhoNome.nativeElement.click();
    expect(host.ultimoEstado()).toMatchObject({ ordenarPor: 'nome', direcao: 'desc' });
  });

  it('anuncia a coluna ordenada em aria-sort, e coluna não ordenável não vira botão', () => {
    fixture.debugElement.queryAll(By.css('thead th .ordenar'))[0].nativeElement.click();
    fixture.detectChanges();

    const ths = fixture.debugElement.queryAll(By.css('thead th'));
    expect(ths[0].nativeElement.getAttribute('aria-sort')).toBe('ascending');
    expect(ths[1].nativeElement.getAttribute('aria-sort')).toBe('none');
    // Coluna com `ordenavel: false` não tem botão nem aria-sort.
    expect(ths[2].query(By.css('.ordenar'))).toBeNull();
    expect(ths[2].nativeElement.getAttribute('aria-sort')).toBeNull();
  });

  it('a busca é debounced e volta pra primeira página', () => {
    host.estado.set(estadoInicialTabela({ pagina: 3 }));
    fixture.detectChanges();

    const input = fixture.debugElement.query(By.css('.tabela-busca input')).nativeElement;
    input.value = 'cafe';
    input.dispatchEvent(new Event('input'));

    // Antes do tempo de espera, nenhuma consulta nova.
    vi.advanceTimersByTime(200);
    expect(host.ultimoEstado()).toBeNull();

    vi.advanceTimersByTime(200);
    expect(host.ultimoEstado()).toMatchObject({ busca: 'cafe', pagina: 1 });
  });

  it('paginador mostra a posição e navega, travando nas pontas', () => {
    host.total.set(25);
    fixture.detectChanges();

    expect(
      fixture.debugElement.query(By.css('.tabela-contador')).nativeElement.textContent,
    ).toContain('Mostrando 1–10 de 25');
    const [anterior, proxima] = fixture.debugElement.queryAll(By.css('.paginador button'));
    expect(anterior.nativeElement.disabled).toBe(true);

    proxima.nativeElement.click();
    expect(host.ultimoEstado()).toMatchObject({ pagina: 2 });

    fixture.detectChanges();
    expect(
      fixture.debugElement.query(By.css('.paginador-posicao')).nativeElement.textContent,
    ).toContain('Página 2 de 3');
  });

  it('trocar o tamanho da página reinicia na primeira', () => {
    host.estado.set(estadoInicialTabela({ pagina: 4 }));
    fixture.detectChanges();

    const opcoes = fixture.debugElement.queryAll(By.css('.tabela-tamanho-opcoes button'));
    opcoes[1].nativeElement.click();

    expect(host.ultimoEstado()).toMatchObject({ tamanhoPagina: 25, pagina: 1 });
  });

  it('linha destacada e célula com tom recebem as classes de realce', () => {
    const linhas = fixture.debugElement.queryAll(By.css('tbody tr'));

    expect(linhas[0].classes['destacada']).toBe(true);
    expect(linhas[1].classes['destacada']).toBeFalsy();
    expect(linhas[0].queryAll(By.css('td'))[1].nativeElement.className).toContain('celula-perigo');
  });

  it('sem linhas mostra a mensagem de vazio; carregando mostra o spinner', () => {
    host.linhas.set([]);
    host.total.set(0);
    fixture.detectChanges();
    expect(fixture.debugElement.query(By.css('.linha-status')).nativeElement.textContent).toContain(
      'Nada aqui.',
    );

    host.carregando.set(true);
    fixture.detectChanges();
    expect(fixture.debugElement.query(By.css('.linha-status')).nativeElement.textContent).toContain(
      'Carregando',
    );
  });

  it('as ações vêm do template da página, com a linha no contexto', () => {
    const acoes = fixture.debugElement.queryAll(By.css('.acao-teste'));
    expect(acoes).toHaveLength(2);

    acoes[1].nativeElement.click();

    expect(host.acionada()).toBe(2);
  });

  it('clicar em qualquer lugar da linha abre o registro', () => {
    (fixture.nativeElement.querySelectorAll('tbody td')[1] as HTMLElement).click();

    expect(host.aberta()).toBe(1);
  });

  it('clicar em Ações faz só a ação, sem abrir o registro', () => {
    (fixture.nativeElement.querySelector('.acao-teste') as HTMLButtonElement).click();

    expect(host.acionada()).toBe(1);
    expect(host.aberta()).toBeNull();
  });

  it('Enter na linha também abre (teclado)', () => {
    const linha = fixture.nativeElement.querySelectorAll('tbody tr')[1] as HTMLElement;
    expect(linha.getAttribute('tabindex')).toBe('0');

    linha.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));

    expect(host.aberta()).toBe(2);
  });

  it('limiteLinhas corta o texto sem aumentar a linha', () => {
    const conteudo = fixture.nativeElement.querySelector(
      'tbody td .celula-conteudo',
    ) as HTMLElement;

    expect(conteudo.classList.contains('limitada')).toBe(true);
    expect(conteudo.style.getPropertyValue('-webkit-line-clamp')).toBe('2');
  });
});
