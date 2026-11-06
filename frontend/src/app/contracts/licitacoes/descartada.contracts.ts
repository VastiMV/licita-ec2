/**
 * Contratos de "Ciclo de Licitação / Descartadas" — as salvas que a equipe
 * tirou da lista antes do prazo vencer. Ver `descartadas` em
 * `apps/licitacoes/encerradas.py`: uma licitação nunca aparece em
 * Descartadas e Encerradas ao mesmo tempo.
 */

import { OportunidadeSalvaResponse } from './oportunidade-salva.contracts';

/** Onde a licitação estava quando foi descartada. */
export type EtapaDescarte = 'oportunidade' | 'cotacao';

export interface DescartadaResponse extends OportunidadeSalvaResponse {
  /** O dia do descarte, `aaaa-mm-dd`. */
  readonly descartada_em: string;
  readonly estava_em: EtapaDescarte;
  readonly cotacao_id: number | null;
  readonly valor_cotado: number | null;
  /** Data e hora do descarte, ISO. */
  readonly removida_em: string;
  readonly removida_por: string | null;
}

export interface DescartadasPagina {
  readonly count: number;
  readonly next: string | null;
  readonly previous: string | null;
  readonly results: readonly DescartadaResponse[];
}

export interface DescartadasParams {
  readonly page?: number;
  readonly page_size?: number;
  readonly ordering?: string;
  readonly busca?: string;
  /** Período do descarte, `aaaa-mm-dd`. */
  readonly data_inicial?: string;
  readonly data_final?: string;
  readonly uf?: string;
}
