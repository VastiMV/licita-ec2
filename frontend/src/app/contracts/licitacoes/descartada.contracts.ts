/**
 * Contratos de "Ciclo de Licitação / Descartadas" — tudo que saiu do ciclo
 * antes de participar do certame: tirada da lista ou prazo vencido, com ou
 * sem cotação. Ver `descartadas` em
 * `apps/licitacoes/encerradas.py`: uma licitação nunca aparece em
 * Descartadas e Encerradas ao mesmo tempo.
 */

import { OportunidadeSalvaResponse } from './oportunidade-salva.contracts';

/** Por que foi descartada: tirada da lista antes do prazo, ou o prazo
 * venceu (com ou sem cotação). */
export type MotivoDescarte =
  'descartada_manual' | 'descartada' | 'prazo_oportunidade' | 'prazo_cotacao' | 'sem_proposta';

export const MOTIVOS_DESCARTE: readonly { value: MotivoDescarte; label: string }[] = [
  { value: 'descartada_manual', label: 'Descartada manualmente' },
  { value: 'descartada', label: 'Tirada da lista' },
  { value: 'prazo_oportunidade', label: 'Prazo venceu sem cotação' },
  { value: 'prazo_cotacao', label: 'Prazo venceu com cotação' },
  { value: 'sem_proposta', label: 'Sem proposta cadastrada' },
];

/** Onde a licitação estava quando foi descartada. */
export type EtapaDescarte = 'oportunidade' | 'cotacao';

export interface DescartadaResponse extends OportunidadeSalvaResponse {
  /** O dia do descarte (a remoção ou o prazo, o que veio primeiro), `aaaa-mm-dd`. */
  readonly descartada_em: string;
  readonly motivo: MotivoDescarte;
  readonly motivo_label: string;
  /** Lixeira: "Descartada manualmente por Carlinhos em 09/11/2026, na etapa
   * Aguardando julgamento. Tinha preço no item 2 (…)". Vazio nos outros. */
  readonly motivo_detalhe?: string;
  readonly estava_em: EtapaDescarte;
  readonly cotacao_id: number | null;
  readonly valor_cotado: number | null;
  /** Data e hora em que tiraram da lista, ISO — `null` quando foi o prazo. */
  readonly removida_em: string | null;
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
  readonly motivo?: string;
  readonly uf?: string;
}
