import { Component, DestroyRef, ElementRef, computed, effect, inject, signal } from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { Router, RouterLink } from '@angular/router';
import { DOCUMENT, NgTemplateOutlet } from '@angular/common';
import { catchError, map, of, switchMap, timer } from 'rxjs';

import {
  Notificacao,
  NotificacoesResponse,
  TipoNotificacao,
} from '../../contracts/notificacoes/notificacoes.contracts';
import { RelatorioCabecalho } from '../../contracts/licitacoes/relatorio.contracts';
import { ModalService } from '../../shared/overlay/modal.service';
import { NotificacoesService } from '../../services/notificacoes/notificacoes.service';

import { EstadoSentinelaResponse } from '../../contracts/sentinela/sentinela.contracts';
import { SentinelaService } from '../../services/sentinela/sentinela.service';

import { EmpresasService } from '../../services/empresas/empresas.service';
import { RadarService } from '../../services/licitacoes/radar.service';
import { IconComponent } from '../../shared/ui/icon/icon.component';

type Painel = 'sentinela' | 'avisos';

/**
 * O topo da tela, como no protótipo "Licita v1.0": de quem é o Licita
 * (empresa e CNPJ), o **Radar** (sugestões), o estado da **Sentinela** e o
 * **sino** de avisos.
 *
 * Cada um mostra o estado **verdadeiro**: o Radar, quantas sugestões há
 * agora (GEN-68, 14/11/2026 — relido a cada 5 min; clicar abre a lista); a
 * Sentinela mostra o que ela disse por último (`GET sentinela/estado/`,
 * relido a cada minuto) — verde só quando ela está lendo de fato. Um "lendo"
 * de mentira faria a operação confiar num vigia que não está vigiando.
 */
@Component({
  selector: 'app-topo-status',
  imports: [IconComponent, NgTemplateOutlet, RouterLink],
  templateUrl: './topo-status.component.html',
  styleUrl: './topo-status.component.scss',
  host: {
    '(document:click)': 'fecharSeFora($event)',
    '(document:keydown.escape)': 'aberto.set(null)',
  },
})
export class TopoStatusComponent {
  private readonly elemento = inject(ElementRef<HTMLElement>);
  private readonly servicoSentinela = inject(SentinelaService);
  private readonly servicoAvisos = inject(NotificacoesService);
  private readonly modal = inject(ModalService);
  private readonly router = inject(Router);

  private readonly radar = inject(RadarService);
  /** O número do botão Radar (GEN-68). Falha = 0: o botão continua lá. */
  protected readonly radarTotal = toSignal(
    timer(0, 300_000).pipe(
      switchMap(() => this.radar.total().pipe(catchError(() => of(0)))),
    ),
    { initialValue: 0 },
  );

  /** O sino (09/11/2026): relido a cada minuto. */
  protected readonly avisos = signal<NotificacoesResponse | null>(null);
  /** O número vermelho: só "Precisa de você" (GEN-104, 19/11/2026). */
  protected readonly naoLidas = computed(() => this.avisos()?.nao_lidas ?? 0);
  protected readonly paraSaberNaoLidas = computed(() => this.avisos()?.para_saber_nao_lidas ?? 0);
  protected readonly precisa = computed(() => this.avisos()?.precisa ?? []);
  protected readonly paraSaber = computed(() => this.avisos()?.para_saber ?? []);
  /** "Para saber" começa recolhido. */
  protected readonly paraSaberAberto = signal(false);

  /**
   * Chamar a atenção (GEN-104): enquanto houver "Precisa de você" não lido
   * que ele ainda não viu (não abriu o sino depois que chegou), o sino treme
   * e o título da aba pisca. Abrir o sino para os dois.
   */
  private readonly vistoAte = signal(0);
  private readonly urgenteNovo = computed(
    () =>
      this.precisa().find((a) => !a.lida && a.id > this.vistoAte()) ?? null,
  );
  protected readonly chamando = computed(() => this.urgenteNovo() !== null);

  private readonly documento = inject(DOCUMENT);

  constructor() {
    const destroy = inject(DestroyRef);
    timer(0, 60_000)
      .pipe(
        switchMap(() => this.servicoAvisos.listar().pipe(catchError(() => of(null)))),
        takeUntilDestroyed(destroy),
      )
      .subscribe((resposta) => {
        if (resposta) this.avisos.set(resposta);
      });

    // Título da aba piscando: "🔴 Pregoeiro! · Licita" ↔ "Licita".
    effect((onCleanup) => {
      const aviso = this.urgenteNovo();
      if (!aviso) return;
      const prefixo = `🔴 ${chamadaDoTitulo(aviso.tipo)} · `;
      let ligado = false;
      const piscar = setInterval(() => {
        const base = this.documento.title.replace(/^🔴 [^·]+ · /, '');
        ligado = !ligado;
        this.documento.title = ligado ? prefixo + base : base;
      }, 1000);
      onCleanup(() => {
        clearInterval(piscar);
        this.documento.title = this.documento.title.replace(/^🔴 [^·]+ · /, '');
      });
    });
  }

  private recarregarAvisos(): void {
    this.servicoAvisos
      .listar()
      .subscribe({ next: (r) => this.avisos.set(r), error: () => undefined });
  }

  /** Resultado do botão "Testar Telegram". */
  protected readonly testeTelegram = signal<string>('');

  protected testarTelegram(): void {
    this.testeTelegram.set('Mandando…');
    this.servicoAvisos.testarTelegram().subscribe({
      next: (r) =>
        this.testeTelegram.set(
          !r.ligado
            ? 'O Telegram ainda não está ligado no servidor.'
            : `Teste enviado para ${r.enviados} de ${r.chats} pessoa${r.chats === 1 ? '' : 's'}.`,
        ),
      error: () => this.testeTelegram.set('Não consegui mandar o teste agora.'),
    });
  }

  protected marcarTodas(): void {
    this.servicoAvisos
      .marcarLidas()
      .subscribe({ next: () => this.recarregarAvisos(), error: () => undefined });
  }

  /** Abre o que o aviso diz: resultado e relatório abrem o relatório da
   * licitação; o resto, a Torre. E marca como lido. */
  protected abrirAviso(aviso: Notificacao): void {
    this.aberto.set(null);
    if (!aviso.lida) {
      this.servicoAvisos
        .marcarLidas([aviso.id])
        .subscribe({ next: () => this.recarregarAvisos(), error: () => undefined });
    }
    if (aviso.oportunidade_id && (aviso.tipo === 'resultado' || aviso.tipo === 'relatorio')) {
      const cabecalho: RelatorioCabecalho = { id: aviso.oportunidade_id, titulo: aviso.titulo };
      // Carregado só quando abre: o topo está em todas as telas.
      void import('../../pages/torre/relatorio-modal/relatorio-modal.component').then((m) =>
        this.modal
          .abrir<void, RelatorioCabecalho>(m.RelatorioModalComponent, cabecalho)
          .subscribe(),
      );
      return;
    }
    void this.router.navigate(['/torre']);
  }

  protected quando(iso: string): string {
    const data = new Date(iso);
    return data.toLocaleString('pt-BR', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  /** A primeira empresa ativa (a Inside é uma só). Sem empresa, nada. */
  protected readonly empresa = toSignal(
    inject(EmpresasService)
      .opcoes()
      .pipe(
        map((empresas) => empresas[0] ?? null),
        catchError(() => of(null)),
      ),
    { initialValue: null },
  );

  protected readonly aberto = signal<Painel | null>(null);

  private readonly sentinela = toSignal(
    timer(0, 60_000).pipe(
      switchMap(() => this.servicoSentinela.estado().pipe(catchError(() => of(null)))),
    ),
    { initialValue: null as EstadoSentinelaResponse | null },
  );

  /** O que o botão mostra: a cor (classe) e o texto. */
  protected readonly vigia = computed(() => vigiaDe(this.sentinela(), new Date()));

  protected alternar(painel: Painel): void {
    this.aberto.update((atual) => (atual === painel ? null : painel));
    if (painel === 'avisos') {
      // Abriu o sino: viu o que chegou; para de tremer e de piscar.
      const maior = Math.max(0, ...this.precisa().map((a) => a.id));
      this.vistoAte.set(Math.max(this.vistoAte(), maior));
    }
  }

  protected fecharSeFora(evento: Event): void {
    if (!this.elemento.nativeElement.contains(evento.target as Node)) this.aberto.set(null);
  }
}

/** O que o título da aba grita, por tipo de aviso urgente (GEN-104). */
export function chamadaDoTitulo(tipo: TipoNotificacao): string {
  switch (tipo) {
    case 'mensagem':
      return 'Pregoeiro!';
    case 'convocacao':
      return 'Convocação!';
    case 'desconto':
      return 'Pedido de desconto!';
    case 'recurso':
      return 'Recurso!';
    case 'sentinela':
      return 'Sentinela parada!';
    default:
      return 'Atenção!';
  }
}

export interface Vigia {
  readonly classe: 'ok' | 'atencao' | 'parada';
  readonly texto: string;
  readonly explicacao: string;
}

function haQuanto(iso: string | null, agora: Date): string {
  if (!iso) return '';
  const minutos = Math.max(0, Math.round((agora.getTime() - new Date(iso).getTime()) / 60_000));
  if (minutos < 1) return 'agora';
  if (minutos < 60) return `há ${minutos} min`;
  const horas = Math.round(minutos / 60);
  if (horas < 48) return `há ${horas} h`;
  return `há ${Math.round(horas / 24)} dias`;
}

/** Traduz o estado da Sentinela para o botão do topo. */
export function vigiaDe(estado: EstadoSentinelaResponse | null, agora: Date): Vigia {
  if (!estado || estado.estado === 'nao_instalada') {
    return {
      classe: 'atencao',
      texto: 'não instalada',
      explicacao:
        'A extensão ainda não falou com o Licita. Instale no Chrome do Carlinhos e cole a chave nas opções dela.',
    };
  }
  if (estado.estado === 'precisa_de_voce') {
    return {
      classe: 'atencao',
      texto: 'precisa de você',
      explicacao: `${estado.detalhe || 'A Sentinela precisa de ajuda'}. Abra o Compras.gov no Chrome e entre de novo, se pedir.`,
    };
  }
  if (estado.estado === 'parada') {
    return {
      classe: 'parada',
      texto: `parada ${haQuanto(estado.ultimo_pulso, agora)}`.trim(),
      explicacao:
        'Sem notícia da Sentinela em horário de trabalho. O computador está ligado, com o Chrome aberto?',
    };
  }
  const leitura = estado.ultima_captura
    ? ` Última leitura ${haQuanto(estado.ultima_captura, agora)}.`
    : '';
  return {
    classe: 'ok',
    texto: haQuanto(estado.ultimo_pulso, agora),
    explicacao: `Lendo o Compras.gov na sessão do Carlinhos.${leitura}`,
  };
}
