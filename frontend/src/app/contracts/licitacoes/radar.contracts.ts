/**
 * Contratos do Radar (GEN-68, 14/11/2026): as compras parecidas com as
 * salvas nos últimos 30 dias e com o que a Inside ganhou
 * (`GET licitacoes/radar/`). `itens` está no formato da busca — é o que o
 * card e o "Salvar" leem.
 */

import { OportunidadeResponse } from './oportunidade.contracts';

export interface SugestaoRadarResponse {
  readonly id: number;
  readonly chave: string;
  readonly cnpj_orgao: string;
  readonly ano_compra: string;
  readonly sequencial_compra: string;
  readonly objeto: string;
  readonly orgao_nome: string;
  readonly uasg: string;
  readonly uf: string;
  readonly municipio: string;
  readonly modalidade: string;
  readonly data_publicacao: string | null;
  readonly data_encerramento_proposta: string | null;
  readonly valor_total_estimado: number | null;
  readonly plataforma_id: string;
  readonly link_plataforma: string;
  readonly link_pncp: string;
  readonly itens: readonly OportunidadeResponse[];
  /** O item da base que puxou a sugestão. */
  readonly parecido_com: string;
  /** Puxada por um item que a Inside ganhou (aparece antes). */
  readonly por_ganho: boolean;
  readonly encontrada_em: string;
  /** O dia em que some: 7 dias ou o dia seguinte à abertura da disputa. */
  readonly expira_em: string;
}

export interface RadarPagina {
  readonly count: number;
  readonly next: string | null;
  readonly previous: string | null;
  readonly results: readonly SugestaoRadarResponse[];
}

export interface RadarParams {
  readonly page?: number;
  readonly page_size?: number;
  readonly ordering?: string;
  readonly busca?: string;
  readonly uf?: string;
}
