/**
 * Contratos de "Ciclo de Licitação / Encerradas" — as licitações que saíram
 * do ciclo. O encerramento é calculado no backend (ver
 * `apps/licitacoes/encerradas.py`), nunca gravado.
 */

import { OportunidadeSalvaResponse } from './oportunidade-salva.contracts';

/** Encerrada: quem participou do certame e saiu, ou a compra que ele só
 * acompanha para ver o resultado ("xeretar", 09/11/2026). As chaves são as
 * de `MOTIVOS` em `apps/licitacoes/encerradas.py`. */
export type MotivoEncerramento =
  | 'perdida'
  | 'acompanhando'
  | 'revogada'
  | 'anulada'
  | 'fracassada'
  | 'deserta'
  // Os desfechos do modal do processo (`processo.model.ts`) ainda usam estes.
  | 'desclassificada'
  | 'perdido_disputa'
  | 'falhou_empenho'
  | 'concluido';

export const MOTIVOS_ENCERRAMENTO: readonly { value: MotivoEncerramento; label: string }[] = [
  { value: 'perdida', label: 'Perdida' },
  { value: 'acompanhando', label: 'Acompanhando o resultado' },
  { value: 'revogada', label: 'Revogada' },
  { value: 'anulada', label: 'Anulada' },
  { value: 'fracassada', label: 'Fracassada' },
  { value: 'deserta', label: 'Deserta' },
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
  | 'descartada_manual'
  | 'sem_proposta'
  | 'proposta_retirada'
  | 'prazo_oportunidade'
  | 'prazo_cotacao';

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
