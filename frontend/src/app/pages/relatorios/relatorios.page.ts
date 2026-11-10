import { TitleCasePipe } from '@angular/common';
import { Component, OnInit, computed, inject, signal } from '@angular/core';

import {
  MercadoDoItem,
  RelatorioMensalResponse,
} from '../../contracts/licitacoes/relatorio.contracts';
import { EncerradasService } from '../../services/licitacoes/encerradas.service';
import { moeda } from '../torre/torre.utils';

const MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];

/** "2026-10" → "out/2026". */
export function nomeDoMes(chave: string): string {
  const [ano, mes] = chave.split('-').map(Number);
  return `${MESES[mes - 1]}/${ano}`;
}

/**
 * Relatórios (09/11/2026): simples e limpo. Uma linha por mês — participou,
 * ganhou, perdeu, faturamento, lucro — e, embaixo, **uma linha só** com o
 * "perdeu por pouco", que abre a lista curta ao clicar.
 */
@Component({
  selector: 'app-relatorios-page',
  imports: [TitleCasePipe],
  templateUrl: './relatorios.page.html',
  styleUrl: './relatorios.page.scss',
})
export class RelatoriosPage implements OnInit {
  private readonly servico = inject(EncerradasService);

  protected readonly dados = signal<RelatorioMensalResponse | null>(null);
  protected readonly erro = signal(false);
  protected readonly abertoPorPouco = signal(false);
  protected readonly mercado = signal<readonly MercadoDoItem[] | null>(null);
  protected readonly periodos = ['3', '6', '12', '24'];

  protected readonly moeda = moeda;
  protected readonly nomeDoMes = nomeDoMes;
  protected readonly totais = computed(() => {
    const meses = this.dados()?.meses ?? [];
    const soma = (f: (m: (typeof meses)[number]) => number) => meses.reduce((t, m) => t + f(m), 0);
    const comLucro = meses.filter((m) => m.lucro !== null);
    return {
      participou: soma((m) => m.participou),
      ganhou: soma((m) => m.ganhou),
      perdeu: soma((m) => m.perdeu),
      faturamento: String(soma((m) => Number(m.faturamento))),
      lucro: comLucro.length ? String(comLucro.reduce((t, m) => t + Number(m.lucro), 0)) : null,
    };
  });

  ngOnInit(): void {
    this.servico.relatorioMensal(12).subscribe({
      next: (d) => this.dados.set(d),
      error: () => this.erro.set(true),
    });
    this.servico.relatorioMercado().subscribe({
      next: (m) => this.mercado.set(m),
      error: () => this.mercado.set([]),
    });
  }

  /** Altura da barra (%) — a maior média do item vale 100. */
  protected altura(item: MercadoDoItem, periodo: string): number {
    const medias = this.periodos.map((p) => item.exato[p]?.media ?? 0);
    const maior = Math.max(...medias, item.media_dele ?? 0);
    const media = item.exato[periodo]?.media ?? 0;
    return maior ? Math.max(4, Math.round((media / maior) * 100)) : 0;
  }

  protected real(valor: number | null | undefined): string {
    return valor == null ? '—' : (moeda(String(valor)) ?? '—');
  }

  /** "Cadeira De Rodas Manual Para Locomoção · capacidade: de 171 a 200" — o
   * tipo e a característica que muda (o que vem depois dos dois pontos). */
  protected titulo(item: MercadoDoItem): string {
    return item.descricao.length > 110 ? item.descricao.slice(0, 110) + '…' : item.descricao;
  }

  protected percentual(valor: string): string {
    return Number(valor).toLocaleString('pt-BR', { maximumFractionDigits: 1 }) + '%';
  }
}
