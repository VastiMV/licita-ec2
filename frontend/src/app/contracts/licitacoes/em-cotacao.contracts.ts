/**
 * Contratos de "Ciclo de Licitação / Cotador" — as licitações na etapa
 * Cotação: as salvas que a Torre põe em Preparar › Cotação
 * (`GET licitacoes/cotacoes/`, GEN-87). Preço lançado só no Compras.gov, sem
 * cotação no Licita: os campos da cotação vêm `null`.
 */

import { OportunidadeSalvaResponse } from './oportunidade-salva.contracts';

/** O selo do cartão do quadro (`ciclo.situacao_da_cotacao`). */
export interface SeloCotacao {
  readonly nivel: 'ok' | 'neutro' | 'aviso' | 'alerta';
  readonly texto: string;
  /** O que falta, em ordem de gravidade. */
  readonly faltas: readonly string[];
}

export interface EmCotacaoResponse extends OportunidadeSalvaResponse {
  readonly cotacao_id: number | null;
  readonly valor_cotado: number | null;
  readonly cotacao_atualizada_em: string | null;
  readonly pendencias: number | null;
  readonly selo: SeloCotacao;
}

export interface EmCotacaoPagina {
  readonly count: number;
  readonly next: string | null;
  readonly previous: string | null;
  readonly results: readonly EmCotacaoResponse[];
}

export interface EmCotacaoParams {
  readonly page?: number;
  readonly page_size?: number;
  readonly ordering?: string;
  readonly busca?: string;
}
