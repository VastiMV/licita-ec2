import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';

import { EmpresasService } from '../../services/empresas/empresas.service';
import { TopoStatusComponent } from './topo-status.component';

describe('TopoStatusComponent', () => {
  let fixture: ComponentFixture<TopoStatusComponent>;
  let el: HTMLElement;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [TopoStatusComponent],
      providers: [
        provideRouter([]),
        {
          provide: EmpresasService,
          useValue: {
            opcoes: () =>
              of([{ id: 1, nome: 'Inside Solutions Ltda', cnpj_formatado: '22.015.414/0001-27' }]),
          },
        },
      ],
    });
    fixture = TestBed.createComponent(TopoStatusComponent);
    fixture.detectChanges();
    el = fixture.nativeElement as HTMLElement;
  });

  const clicar = (seletor: string) => {
    (el.querySelector(seletor) as HTMLButtonElement).click();
    fixture.detectChanges();
  };

  it('mostra a empresa, o Radar, a Sentinela e o sino', () => {
    expect(el.querySelector('.empresa')?.textContent).toContain(
      'Inside Solutions Ltda · CNPJ 22.015.414/0001-27',
    );
    expect(el.querySelector('.radar')?.textContent).toContain('em breve');
    expect(el.querySelector('.sentinela')?.textContent).toContain('não instalada');
    expect(el.querySelector('.sino')).toBeTruthy();
  });

  it('a Sentinela não finge que está lendo', () => {
    expect(el.querySelector('.sentinela')?.textContent).not.toContain('há');
    expect(el.querySelector('.sentinela .ponto.verde')).toBeNull();
  });

  it('clicar abre o painel que explica; clicar de novo fecha', () => {
    clicar('.sentinela');
    expect(el.querySelector('.painel')?.textContent).toContain('extensão do Chrome');

    clicar('.sentinela');
    expect(el.querySelector('.painel')).toBeNull();
  });

  it('só um painel aberto por vez', () => {
    clicar('.radar');
    clicar('.sino');

    const paineis = el.querySelectorAll('.painel');
    expect(paineis.length).toBe(1);
    expect(paineis[0].textContent).toContain('Nenhum aviso ainda');
  });
});
