import { DIALOG_DATA, DialogRef } from '@angular/cdk/dialog';
import { Component, OnInit, inject, signal } from '@angular/core';

import { SugestaoRadarResponse } from '../../../contracts/licitacoes/radar.contracts';
import { LicitacoesService } from '../../../services/licitacoes/licitacoes.service';
import { OportunidadesSalvasService } from '../../../services/licitacoes/oportunidades-salvas.service';
import { ModalShellComponent } from '../../../shared/overlay/modal-shell/modal-shell.component';
import { ButtonComponent } from '../../../shared/ui/button/button.component';
import { ToastService } from '../../../shared/ui/toast/toast.service';
import { EditalCardComponent } from '../../oportunidades/edital-card/edital-card.component';
import { DetalheEstado, EditalCard } from '../../oportunidades/edital-card/edital-card.model';

/** `'salva'` quando a pessoa salvou: a sugestão sai do Radar. */
export type RadarModalResultado = 'salva' | undefined;

/**
 * Uma sugestão do Radar (GEN-68): o **mesmo card** da busca. "Salvar" leva a
 * compra para Oportunidades (e ela sai do Radar); daí ele decide se vê o
 * edital, o PNCP ou o portal — pelo próprio card.
 */
@Component({
  selector: 'app-radar-modal',
  imports: [ModalShellComponent, EditalCardComponent, ButtonComponent],
  templateUrl: './radar-modal.component.html',
  styleUrl: './radar-modal.component.scss',
})
export class RadarModalComponent implements OnInit {
  private readonly dialogRef = inject(DialogRef<RadarModalResultado>);
  private readonly licitacoes = inject(LicitacoesService);
  private readonly salvas = inject(OportunidadesSalvasService);
  private readonly toast = inject(ToastService);

  protected readonly sugestao = inject<SugestaoRadarResponse>(DIALOG_DATA);

  protected readonly card: EditalCard = {
    chave: this.sugestao.chave,
    contratacao: this.sugestao.itens[0],
    itens: this.sugestao.itens,
  };

  protected readonly detalhe = signal<DetalheEstado | undefined>(undefined);
  protected readonly salvando = signal(false);

  ngOnInit(): void {
    const { cnpj_orgao, ano_compra, sequencial_compra } = this.sugestao;
    this.detalhe.set({ carregando: true, documentos: [], capag: null, plataforma: null, erro: false });
    this.licitacoes.detalharCompra(cnpj_orgao, ano_compra, sequencial_compra).subscribe({
      next: (dados) =>
        this.detalhe.set({
          carregando: false,
          documentos: dados.documentos,
          capag: dados.capag ?? null,
          plataforma: dados.plataforma,
          erro: false,
        }),
      error: () =>
        this.detalhe.set({ carregando: false, documentos: [], capag: null, plataforma: null, erro: true }),
    });
  }

  protected fechar(): void {
    this.dialogRef.close();
  }

  protected salvar(): void {
    if (this.salvando()) return;
    this.salvando.set(true);
    const detalhe = this.detalhe();
    this.salvas
      .salvar({
        itens: this.card.itens,
        capag: detalhe?.capag ?? null,
        plataforma: detalhe?.plataforma ?? null,
      })
      .subscribe({
        next: () => {
          this.toast.sucesso('Oportunidade salva — está em Oportunidades.');
          this.dialogRef.close('salva');
        },
        error: () => {
          this.salvando.set(false);
          this.toast.erro('Não foi possível salvar a oportunidade agora.');
        },
      });
  }

  protected baixarEdital(): void {
    const url = this.detalhe()?.documentos[0]?.url;
    if (url) window.open(url, '_blank', 'noopener');
  }
}
