import { Component, OnInit, computed, inject, signal } from '@angular/core';

import { RelatorioMensalResponse } from '../../contracts/licitacoes/relatorio.contracts';
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
  templateUrl: './relatorios.page.html',
  styleUrl: './relatorios.page.scss',
})
export class RelatoriosPage implements OnInit {
  private readonly servico = inject(EncerradasService);

  protected readonly dados = signal<RelatorioMensalResponse | null>(null);
  protected readonly erro = signal(false);
  protected readonly abertoPorPouco = signal(false);

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
  }

  protected percentual(valor: string): string {
    return Number(valor).toLocaleString('pt-BR', { maximumFractionDigits: 1 }) + '%';
  }
}
