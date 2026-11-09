import { DIALOG_DATA, DialogRef } from '@angular/cdk/dialog';
import { Component, OnInit, inject, signal } from '@angular/core';

import {
  ItemDoRelatorio,
  PropostaDoRelatorio,
  RelatorioCabecalho,
  RelatorioResponse,
} from '../../../contracts/licitacoes/relatorio.contracts';
import { EncerradasService } from '../../../services/licitacoes/encerradas.service';
import { normalizarTitulo } from '../../oportunidades/edital-card/edital-card.utils';
import { moeda } from '../torre.utils';

const SITUACAO: Record<string, string> = {
  '1': 'desclassificada',
  '2': 'desclassificada',
  '9': 'desclassificada',
  '3': 'aceita',
  '4': 'habilitada',
  '5': 'inabilitada',
  '6': 'adjudicada',
};

/** "+R$ 374,96 (45,4% acima)" · "R$ 12,00 abaixo (1,2%)" · "mesmo valor". */
export function textoDaDiferenca(item: ItemDoRelatorio): string | null {
  if (item.diferenca == null) return null;
  const valor = Number(item.diferenca);
  if (valor === 0) return 'mesmo valor do vencedor';
  const pct = Math.abs(Number(item.diferenca_percentual ?? 0)).toLocaleString('pt-BR', {
    maximumFractionDigits: 1,
  });
  const quanto = moeda(String(Math.abs(valor)));
  return valor > 0 ? `${quanto} acima (${pct}%)` : `${quanto} abaixo (${pct}%)`;
}

export function situacaoDaProposta(p: PropostaDoRelatorio): string {
  return SITUACAO[p.situacao] ?? '';
}

/**
 * O relatório da licitação (pedido de 08/11/2026): item a item, quem ganhou
 * (ou está em 1º), marca, modelo, valor, e quanto a empresa ficou de
 * diferença; embaixo, a lista inteira de propostas. Só consulta.
 */
@Component({
  selector: 'app-relatorio-modal',
  templateUrl: './relatorio-modal.component.html',
  styleUrl: './relatorio-modal.component.scss',
})
export class RelatorioModalComponent implements OnInit {
  private readonly dialogRef = inject(DialogRef<void>);
  private readonly service = inject(EncerradasService);

  protected readonly cab = inject<RelatorioCabecalho>(DIALOG_DATA);
  protected readonly relatorio = signal<RelatorioResponse | null>(null);
  protected readonly erro = signal(false);

  protected readonly moeda = moeda;
  protected readonly titulo = normalizarTitulo;
  protected readonly diferenca = textoDaDiferenca;
  protected readonly situacao = situacaoDaProposta;

  ngOnInit(): void {
    this.service.relatorio(this.cab.id).subscribe({
      next: (r) => this.relatorio.set(r),
      error: () => this.erro.set(true),
    });
  }

  protected fechar(): void {
    this.dialogRef.close();
  }
}
