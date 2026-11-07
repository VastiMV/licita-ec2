/**
 * Contratos de "Ciclo de Licitação / Encerradas" — as licitações que saíram
 * do ciclo. O encerramento é calculado no backend (ver
 * `apps/licitacoes/encerradas.py`), nunca gravado.
 */

import { OportunidadeSalvaResponse } from './oportunidade-salva.contracts';

/** Encerrada é só quem chegou a cotar. Tirada da lista e vencida sem
 * cotação são Descartadas (ver `encerradas.py`). Perdida na disputa e
 * falha no empenho entram aqui com as etapas. */
export type MotivoEncerramento = 'prazo_cotacao';

export const MOTIVOS_ENCERRAMENTO: readonly { value: MotivoEncerramento; label: string }[] = [
  { value: 'prazo_cotacao', label: 'Prazo perdido na cotação' },
];

export interface EncerradaResponse extends OportunidadeSalvaResponse {
  readonly encerrada_em: string;
  readonly motivo: MotivoEncerramento;
  readonly motivo_label: string;
  readonly cotacao_id: number | null;
  readonly valor_cotado: number | null;
  readonly removida_em: string | null;
  readonly removida_por: string | null;
}

/** O que o modal do processo precisa de uma linha — Encerradas e Cotador
 * abrem o mesmo modal. */
export type ProcessoCabecalho = OportunidadeSalvaResponse & {
  readonly cotacao_id: number | null;
  readonly valor_cotado: number | null;
};

export interface EncerradasPagina {
  readonly count: number;
  readonly next: string | null;
  readonly previous: string | null;
  readonly results: readonly EncerradaResponse[];
}

export interface EncerradasParams {
  readonly page?: number;
  readonly page_size?: number;
  readonly ordering?: string;
  readonly busca?: string;
  /** Período de encerramento, `aaaa-mm-dd`. */
  readonly data_inicial?: string;
  readonly data_final?: string;
  readonly motivo?: string;
  readonly uf?: string;
}

// ---------- o processo (`GET licitacoes/salvas/<id>/processo/`) ----------

export type EtapaCiclo = 'oportunidade' | 'cotacao' | 'proposta' | 'disputa' | 'empenho';

/** Os desfechos de hoje são os motivos de Encerradas mais o descarte (que
 * não aparece em Encerradas, mas o processo de uma descartada ainda conta
 * quem tirou da lista); desclassificada, perdida na disputa, falha no
 * empenho e concluído entram com as etapas. */
export type TipoDesfecho =
  | MotivoEncerramento
  | 'descartada'
  | 'prazo_oportunidade'
  | 'desclassificada'
  | 'perdido_disputa'
  | 'falhou_empenho'
  | 'concluido';

export interface EventoDoProcesso {
  readonly id: number;
  /** `oportunidade_salva`, `cotacao_criada`, `cotacao_atualizada`,
   * `prazo_encerrado`, `removida`… */
  readonly tipo: string;
  readonly etapa: EtapaCiclo;
  readonly texto: string;
  /** `null` = evento do sistema. */
  readonly autor: string | null;
  readonly data: string;
  readonly valor: number | null;
}

export interface DesfechoProcesso {
  readonly tipo: TipoDesfecho;
  /** Data (prazo) ou data e hora (descarte), ISO. */
  readonly data: string;
  readonly por: string | null;
  /** O "por que parou aqui", já escrito pelo backend. */
  readonly porque: string;
}

export interface ProcessoResponse {
  readonly id: number;
  readonly etapa: EtapaCiclo;
  /** `null` = processo em andamento. */
  readonly desfecho: DesfechoProcesso | null;
  readonly eventos: readonly EventoDoProcesso[];
}
