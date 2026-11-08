import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';

import { EstadoSentinelaResponse } from '../../contracts/sentinela/sentinela.contracts';
import { EmpresasService } from '../../services/empresas/empresas.service';
import { SentinelaService } from '../../services/sentinela/sentinela.service';
import { TopoStatusComponent, vigiaDe } from './topo-status.component';

describe('TopoStatusComponent', () => {
  let fixture: ComponentFixture<TopoStatusComponent>;
  let el: HTMLElement;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [TopoStatusComponent],
      providers: [
        provideRouter([]),
        {
          provide: SentinelaService,
          useValue: {
            estado: () =>
              of({
                estado: 'nao_instalada',
                ultimo_pulso: null,
                ultima_captura: null,
                detalhe: '',
              }),
          },
        },
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
    expect(el.querySelector('.painel')?.textContent).toContain('Instale no Chrome');

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

describe('vigiaDe (o botão da Sentinela)', () => {
  const agora = new Date('2026-11-09T10:30:00-03:00');
  const estado = (e: Partial<EstadoSentinelaResponse>): EstadoSentinelaResponse => ({
    estado: 'ok',
    ultimo_pulso: '2026-11-09T10:28:00-03:00',
    ultima_captura: '2026-11-09T10:10:00-03:00',
    detalhe: '',
    ...e,
  });

  it('lendo: verde, com há quanto tempo', () => {
    const v = vigiaDe(estado({}), agora);

    expect(v.classe).toBe('ok');
    expect(v.texto).toBe('há 2 min');
    expect(v.explicacao).toContain('Última leitura há 20 min');
  });

  it('sessão caiu: âmbar, pedindo o Carlinhos', () => {
    const v = vigiaDe(
      estado({ estado: 'precisa_de_voce', detalhe: 'A sessão do Compras.gov caiu' }),
      agora,
    );

    expect(v.classe).toBe('atencao');
    expect(v.texto).toBe('precisa de você');
    expect(v.explicacao).toContain('A sessão do Compras.gov caiu');
  });

  it('calada em horário de trabalho: vermelho', () => {
    const v = vigiaDe(
      estado({ estado: 'parada', ultimo_pulso: '2026-11-09T10:00:00-03:00' }),
      agora,
    );

    expect(v.classe).toBe('parada');
    expect(v.texto).toBe('parada há 30 min');
  });

  it('nunca falou (ou sem resposta do Licita): não instalada, nunca verde', () => {
    expect(vigiaDe(null, agora).texto).toBe('não instalada');
    expect(vigiaDe(null, agora).classe).toBe('atencao');
  });
});
