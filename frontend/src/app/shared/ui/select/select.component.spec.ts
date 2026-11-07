import { Component, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { FormsModule } from '@angular/forms';
import { By } from '@angular/platform-browser';

import { SelectComponent, SelectOption } from './select.component';

const MODALIDADES: SelectOption[] = [
  { value: '6', label: 'Pregão - Eletrônico' },
  { value: '8', label: 'Dispensa de Licitação' },
];

@Component({
  imports: [FormsModule, SelectComponent],
  template: `<app-select
    label="Modalidade"
    [options]="opcoes"
    [ngModel]="valor()"
    (ngModelChange)="valor.set($event)"
  />`,
})
class HostComponent {
  opcoes = MODALIDADES;
  valor = signal('');
}

describe('SelectComponent', () => {
  let fixture: ComponentFixture<HostComponent>;
  let host: HostComponent;

  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [HostComponent] });
    fixture = TestBed.createComponent(HostComponent);
    host = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('renderiza uma option por item de options(), mais o placeholder', () => {
    const options = fixture.debugElement.queryAll(By.css('option'));
    expect(options).toHaveLength(3);
    expect(options[0].nativeElement.textContent.trim()).toBe('Todas');
    expect(options[1].nativeElement.textContent.trim()).toBe('Pregão - Eletrônico');
  });

  it('propaga a seleção para o ngModel do host', () => {
    const select: HTMLSelectElement = fixture.debugElement.query(By.css('select')).nativeElement;
    select.value = '8';
    select.dispatchEvent(new Event('change'));
    fixture.detectChanges();

    expect(host.valor()).toBe('8');
  });

  it('reflete no select um valor setado programaticamente pelo host (writeValue)', async () => {
    host.valor.set('8');
    fixture.detectChanges();
    // NgModel aplica o writeValue de forma assíncrona — ver o mesmo
    // comentário em input-text.component.spec.ts.
    await fixture.whenStable();
    fixture.detectChanges();

    const select: HTMLSelectElement = fixture.debugElement.query(By.css('select')).nativeElement;
    expect(select.value).toBe('8');
  });
});

@Component({
  imports: [FormsModule, SelectComponent],
  template: `<app-select
    label="Período"
    [options]="opcoes"
    [opcaoVazia]="false"
    [ngModel]="valor()"
    (ngModelChange)="valor.set($event)"
  />`,
})
class HostSemVazioComponent {
  opcoes = MODALIDADES;
  valor = signal('8');
}

describe('SelectComponent sem opção vazia, com valor inicial', () => {
  it('mostra o valor inicial (não cai na primeira opção) e não tem placeholder', async () => {
    TestBed.configureTestingModule({ imports: [HostSemVazioComponent] });
    const fixture = TestBed.createComponent(HostSemVazioComponent);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    const select: HTMLSelectElement = fixture.debugElement.query(By.css('select')).nativeElement;
    expect(select.options).toHaveLength(2);
    expect(select.value).toBe('8');
    expect(select.selectedOptions[0].textContent?.trim()).toBe('Dispensa de Licitação');
  });
});
