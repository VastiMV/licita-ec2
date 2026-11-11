import { DIALOG_DATA, DialogRef } from '@angular/cdk/dialog';
import { NgTemplateOutlet } from '@angular/common';
import { Component, OnInit, computed, inject, signal } from '@angular/core';

import {
  ProcessoCabecalho,
  ProcessoResponse,
} from '../../../../contracts/licitacoes/encerrada.contracts';
import { CotadorService } from '../../../../services/cotador/cotador.service';
import { EncerradasService } from '../../../../services/licitacoes/encerradas.service';
import { ToastService } from '../../../../shared/ui/toast/toast.service';
import { formatarData, formatarMoeda } from '../../../oportunidades/edital-card/edital-card.utils';
import { abrirNoCompras } from '../../../torre/abrir-no-compras';
import {
  DESFECHOS,
  ETAPAS,
  NoLinhaDoTempo,
  brl,
  dia,
  diaAno,
  diasEntre,
  hora,
  estadoDaFase,
  gruposDaLinhaDoTempo,
  indiceAtual,
  iniciais,
  narrar,
  textoDoDesfecho,
  tendencia,
} from './processo.model';

const COMPRAS_GOV = 'https://cnetmobile.estaleiro.serpro.gov.br/';

/** O que o modal pede a quem abriu: hoje, só abrir a cotação. */
export type ProcessoModalResultado = 'cotacao';

/**
 * O processo de uma licitação: onde está ou onde parou, e por quê. Fases
 * clicáveis, linha do tempo por etapa e a narração da fase escolhida.
 * Desenho: `docs/design/modal-processo/`. Somente consulta.
 */
@Component({
  selector: 'app-processo-modal',
  imports: [NgTemplateOutlet],
  templateUrl: './processo-modal.component.html',
  styleUrl: './processo-modal.component.scss',
  host: { '(keydown)': 'teclado($event)' },
})
export class ProcessoModalComponent implements OnInit {
  private readonly dialogRef = inject(DialogRef<ProcessoModalResultado>);
  private readonly service = inject(EncerradasService);
  private readonly cotador = inject(CotadorService);
  private readonly toast = inject(ToastService);

  protected readonly cab = inject<ProcessoCabecalho>(DIALOG_DATA);
  protected readonly processo = signal<ProcessoResponse | null>(null);
  protected readonly erro = signal(false);
  protected readonly selecionada = signal(0);
  protected readonly abertos = signal<ReadonlySet<number>>(new Set());
  protected readonly exportando = signal(false);

  protected readonly etapas = ETAPAS;
  protected readonly data = formatarData;
  protected readonly moeda = formatarMoeda;
  protected readonly brl = brl;
  protected readonly dia = dia;
  protected readonly diaAno = diaAno;
  protected readonly iniciais = iniciais;
  protected readonly tendencia = tendencia;

  protected readonly desfecho = computed(() => this.processo()?.desfecho ?? null);
  protected readonly infoDesfecho = computed(() => {
    const d = this.desfecho();
    return d ? DESFECHOS[d.tipo] : null;
  });
  protected readonly tituloDesfecho = computed(() => {
    const d = this.desfecho();
    return d ? textoDoDesfecho(d) : '';
  });
  protected readonly diasDesde = computed(() => {
    const d = this.desfecho();
    return d ? diasEntre(d.data, new Date()) : 0;
  });
  protected readonly nomeEtapaAtual = computed(() => {
    const p = this.processo();
    return p ? ETAPAS[indiceAtual(p)].nome : '';
  });
  protected readonly fases = computed(() => {
    const p = this.processo();
    return p ? ETAPAS.map((_, i) => estadoDaFase(p, i)) : [];
  });
  protected readonly grupos = computed(() => {
    const p = this.processo();
    return p ? gruposDaLinhaDoTempo(p) : [];
  });
  protected readonly narracao = computed(() => {
    const p = this.processo();
    return p ? narrar(p, this.cab, this.selecionada()) : null;
  });
  protected readonly periodoSelecionado = computed(
    () => this.grupos()[this.selecionada()]?.periodo ?? '',
  );
  protected readonly temCotacao = computed(() => this.cab.cotacao_id !== null);

  ngOnInit(): void {
    this.service.processo(this.cab.id).subscribe({
      next: (processo) => {
        this.processo.set(processo);
        this.selecionada.set(indiceAtual(processo));
      },
      error: () => this.erro.set(true),
    });
  }

  protected selecionar(i: number): void {
    this.selecionada.set(Math.max(0, Math.min(ETAPAS.length - 1, i)));
  }

  protected teclado(evento: KeyboardEvent): void {
    if (evento.key === 'ArrowRight') this.selecionar(this.selecionada() + 1);
    if (evento.key === 'ArrowLeft') this.selecionar(this.selecionada() - 1);
  }

  protected alternarGrupo(chave: number): void {
    this.abertos.update((atual) => {
      const novo = new Set(atual);
      if (novo.has(chave)) novo.delete(chave);
      else novo.add(chave);
      return novo;
    });
  }

  /** Chave estável de um bloco agrupado: o id do primeiro evento dele. */
  protected chaveDoGrupo(no: NoLinhaDoTempo): number {
    return no.tipo === 'grupo' ? no.eventos[0].id : -1;
  }

  /** "31/08 · 10:58" — ou só o dia, quando o evento não tem hora. */
  protected quando(iso: string): string {
    return iso.length > 10 ? `${dia(iso)} · ${hora(iso)}` : dia(iso);
  }

  protected primeiroNome(nome: string): string {
    return nome.split(/[\s@]/)[0];
  }

  protected exportar(): void {
    const id = this.cab.cotacao_id;
    if (id === null) return;
    this.exportando.set(true);
    this.cotador.exportar(id).subscribe({
      next: ({ conteudo, nome }) => {
        this.exportando.set(false);
        const url = URL.createObjectURL(conteudo);
        const link = document.createElement('a');
        link.href = url;
        link.download = nome;
        link.click();
        URL.revokeObjectURL(url);
      },
      error: () => {
        this.exportando.set(false);
        this.toast.erro('Não foi possível gerar a planilha agora.');
      },
    });
  }

  /**
   * Compras.gov: a sessão vale por aba, e uma aba nova cai no login (página
   * inválida — GEN-53/64). Com a Sentinela, quem abre é ela, numa cópia da aba
   * já logada. Outros portais seguem o link normal.
   */
  protected abrirPlataforma(evento: MouseEvent): void {
    const url = this.cab.link_plataforma;
    if (!url?.startsWith(COMPRAS_GOV)) return;
    evento.preventDefault();
    abrirNoCompras(url);
  }

  protected verCotacao(): void {
    this.dialogRef.close('cotacao');
  }

  protected fechar(): void {
    this.dialogRef.close();
  }
}
