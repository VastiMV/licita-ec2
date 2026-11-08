import { DestroyRef, Injectable, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

import { TorreResponse } from '../../contracts/licitacoes/torre.contracts';
import { rotaDaEtapa } from '../../pages/torre/torre.utils';
import { TorreService } from '../../services/licitacoes/torre.service';

/**
 * Quantas licitações há em cada etapa da Torre, para o número ao lado de
 * cada item do menu. A chave é o endereço do item ("/torre/etapa/disputa").
 * Sem dado (carregando ou erro), o menu só não mostra os números.
 */
@Injectable({ providedIn: 'root' })
export class ContagemDoMenuService {
  private readonly torre = inject(TorreService);
  private readonly destroyRef = inject(DestroyRef);

  readonly porEndereco = signal<ReadonlyMap<string, number>>(new Map());

  atualizar(): void {
    this.torre
      .torre()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (resposta) => this.porEndereco.set(contar(resposta)),
        error: () => undefined,
      });
  }
}

export function contar(resposta: TorreResponse): Map<string, number> {
  const mapa = new Map<string, number>();
  for (const estagio of resposta.estagios) {
    for (const etapa of estagio.etapas) mapa.set(rotaDaEtapa(etapa.chave), etapa.total);
  }
  mapa.set('/ciclo/encerradas', resposta.saidas.encerradas);
  mapa.set('/ciclo/descartadas', resposta.saidas.descartadas);
  return mapa;
}
