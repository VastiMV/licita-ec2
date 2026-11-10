import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';

import { EstadoSentinelaResponse } from '../../contracts/sentinela/sentinela.contracts';
import { NotificacoesResponse } from '../../contracts/notificacoes/notificacoes.contracts';
import { ModalService } from '../../shared/overlay/modal.service';
import { EmpresasService } from '../../services/empresas/empresas.service';
import { NotificacoesService } from '../../services/notificacoes/notificacoes.service';
import { SentinelaService } from '../../services/sentinela/sentinela.service';
import { TopoStatusComponent, vigiaDe } from './topo-status.component';

const AVISOS: NotificacoesResponse = {
  nao_lidas: 2,
  itens: [
    {
      id: 7,
      tipo: 'resultado',
      nivel: 'info',
      titulo: 'Resultado · Pregão 9/2026 · item 3',
      texto: 'Ganhou: EMPRESA X · Marca Y · R$ 1.250,00',
      oportunidade_id: 17,
      criada_em: '2026-11-09T10:00:00Z',
      lida: false,
    },
    {
      id: 8,
      tipo: 'convocacao',
      nivel: 'alerta',
      titulo: 'Convocação · Pregão 59/2026 · item 30',
      texto: '',
      oportunidade_id: 20,
      criada_em: '2026-11-09T11:00:00Z',
      lida: false,
    },
  ],
};

describe('TopoStatusComponent', () => {
  let fixture: ComponentFixture<TopoStatusComponent>;
  let el: HTMLElement;
  let avisos: {
    listar: ReturnType<typeof vi.fn>;
    marcarLidas: ReturnType<typeof vi.fn>;
    testarTelegram: ReturnType<typeof vi.fn>;
  };
  let modal: { abrir: ReturnType<typeof vi.fn> };

  beforeEach(() => {
    avisos = {
      listar: vi.fn(() => of(AVISOS)),
      marcarLidas: vi.fn(() => of({ ok: true })),
      testarTelegram: vi.fn(() => of({ ligado: true, enviados: 2, chats: 2 })),
    };
    modal = { abrir: vi.fn(() => of(undefined)) };
    TestBed.configureTestingModule({
      imports: [TopoStatusComponent],
      providers: [
        provideRouter([]),
        { provide: NotificacoesService, useValue: avisos },
        { provide: ModalService, useValue: modal },
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

  const avisosChegarem = async () => {
    await new Promise((r) => setTimeout(r, 0));
    fixture.detectChanges();
  };

  it('o sino mostra quantos avisos novos e a lista', async () => {
    await avisosChegarem();
    expect(el.querySelector('.sino .contador')?.textContent?.trim()).toBe('2');

    clicar('.sino');

    const itens = [...el.querySelectorAll('.aviso')];
    expect(itens.length).toBe(2);
    expect(itens[1].getAttribute('data-nivel')).toBe('alerta');
    expect(itens[0].textContent).toContain('EMPRESA X');
  });

  it('clicar num resultado abre o relatório e marca como lido', async () => {
    await avisosChegarem();
    clicar('.sino');
    clicar('.aviso');
    await new Promise((r) => setTimeout(r, 50));

    expect(avisos.marcarLidas).toHaveBeenCalledWith([7]);
    expect(modal.abrir).toHaveBeenCalledWith(expect.anything(), {
      id: 17,
      titulo: AVISOS.itens[0].titulo,
    });
  });

  it('"Testar Telegram" diz para quantos foi', async () => {
    await avisosChegarem();
    clicar('.sino');
    clicar('.telegram .link');

    expect(el.querySelector('.telegram')?.textContent).toContain(
      'Teste enviado para 2 de 2 pessoas',
    );
  });

  it('marcar todos como lidos', async () => {
    await avisosChegarem();
    clicar('.sino');
    clicar('.avisos-topo .link');

    expect(avisos.marcarLidas).toHaveBeenCalledWith();
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
