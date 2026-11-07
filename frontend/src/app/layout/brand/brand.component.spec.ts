import { ComponentFixture, TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { provideRouter } from '@angular/router';

import { BrandComponent } from './brand.component';

describe('BrandComponent', () => {
  let fixture: ComponentFixture<BrandComponent>;

  const img = () =>
    fixture.debugElement.query(By.css('img.brand-logo')).nativeElement as HTMLImageElement;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [BrandComponent],
      providers: [provideRouter([])],
    });
    fixture = TestBed.createComponent(BrandComponent);
    fixture.detectChanges();
  });

  it('mostra o logo com nome, e o nome no texto alternativo', () => {
    expect(img().getAttribute('src')).toBe('marca/logo-horizontal.png');
    expect(img().alt).toBe('Inside Solutions');
  });

  it('linka pra raiz da aplicação', () => {
    const link = fixture.debugElement.query(By.css('a.brand'));
    expect(link.attributes['href']).toBe('/');
  });

  it('em modo compact, mostra só o símbolo, no quadrado escuro', () => {
    fixture.componentRef.setInput('compact', true);
    fixture.detectChanges();

    expect(img().getAttribute('src')).toBe('marca/simbolo.png');
    expect(fixture.debugElement.query(By.css('a.brand.compact'))).toBeTruthy();
  });

  it('completo traz o logo com a frase (login)', () => {
    fixture.componentRef.setInput('completo', true);
    fixture.detectChanges();

    expect(img().getAttribute('src')).toBe('marca/logo-completo.png');
  });
});
