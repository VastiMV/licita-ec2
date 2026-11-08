import { Component, ElementRef, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { catchError, map, of, switchMap, timer } from 'rxjs';

import { EstadoSentinelaResponse } from '../../contracts/sentinela/sentinela.contracts';
import { SentinelaService } from '../../services/sentinela/sentinela.service';

import { EmpresasService } from '../../services/empresas/empresas.service';
import { IconComponent } from '../../shared/ui/icon/icon.component';

type Painel = 'radar' | 'sentinela' | 'avisos';

/**
 * O topo da tela, como no protótipo "Licita v1.0": de quem é o Licita
 * (empresa e CNPJ), o **Radar** (sugestões), o estado da **Sentinela** e o
 * **sino** de avisos.
 *
 * Cada um mostra o estado **verdadeiro**: o Radar ainda é "em breve"; a
 * Sentinela mostra o que ela disse por último (`GET sentinela/estado/`,
 * relido a cada minuto) — verde só quando ela está lendo de fato. Um "lendo"
 * de mentira faria a operação confiar num vigia que não está vigiando.
 */
@Component({
  selector: 'app-topo-status',
  imports: [IconComponent, RouterLink],
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
  }

  protected fecharSeFora(evento: Event): void {
    if (!this.elemento.nativeElement.contains(evento.target as Node)) this.aberto.set(null);
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
