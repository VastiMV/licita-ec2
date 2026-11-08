/**
 * Contratos da Torre de Controle — ver `apps/licitacoes/torre.py` no
 * backend. A etapa é calculada lá, **por item**, a cada leitura: o cartão da
 * licitação fica na etapa do item da empresa que está mais adiante.
 */

import { OportunidadeSalvaResponse } from './oportunidade-salva.contracts';

export type EstagioTorre = 'preparar' | 'disputar' | 'contratar' | 'receber';

export type EtapaTorre =
  | 'oportunidade'
  | 'cotacao'
  | 'cadastro_proposta'
  | 'disputa'
  | 'aguardando_julgamento'
  | 'julgado_habilitado'
  | 'aguardando_adjudicacao'
  | 'homologado'
  | 'contrato'
  | 'empenho'
  | 'entrega'
  | 'liquidado'
  | 'recebido';

export type NivelEtiqueta = 'alerta' | 'aviso' | 'info';

export interface EtiquetaTorre {
  readonly nivel: NivelEtiqueta;
  readonly texto: string;
}

/** Um item da compra em que a empresa tem proposta. Valores chegam como
 * texto decimal ("15500.00"), como o DRF serializa `Decimal`. */
export interface ItemTorre {
  readonly numero: string;
  readonly descricao: string;
  /** Nula quando o item foi perdido (ver `perdido`). */
  readonly etapa: EtapaTorre | null;
  readonly etapa_rotulo: string;
  /** "Fornecedor habilitado", "Proposta aceita"… — vazio sem situação. */
  readonly situacao: string;
  readonly classificacao: number | null;
  /** 2º lugar em diante: ainda pode ser chamado, fica em cinza. */
  readonly perdendo: boolean;
  /** Por que se perdeu ("proposta desclassificada"); vazio se não. */
  readonly perdido: string;
  readonly quantidade: string | null;
  readonly valor_unitario: string | null;
  readonly valor_total: string | null;
}

export interface CartaoTorre {
  /** Id da oportunidade salva. */
  readonly id: number;
  readonly estagio: EstagioTorre;
  readonly etapa: EtapaTorre;
  readonly etapa_rotulo: string;
  readonly uasg: string;
  readonly orgao_nome: string;
  readonly municipio: string;
  readonly uf: string;
  readonly objeto: string;
  readonly data_encerramento_proposta: string | null;
  readonly valor_total_estimado: string | null;
  readonly link_plataforma: string;
  readonly cotacao_id: number | null;
  /** Só em Preparar: o registro inteiro, para os modais que já existem. */
  readonly salva: OportunidadeSalvaResponse | null;
  readonly itens: readonly ItemTorre[];
  /** Soma dos itens ganhos ou à frente (sem os perdendo). */
  readonly valor_ganho: string | null;
  /** Já ordenadas: alerta, aviso, informação. */
  readonly etiquetas: readonly EtiquetaTorre[];
}

export interface EtapaDoEstagio {
  readonly chave: EtapaTorre;
  readonly rotulo: string;
  readonly total: number;
}

export interface EstagioDaTorre {
  readonly chave: EstagioTorre;
  readonly rotulo: string;
  readonly total: number;
  readonly etapas: readonly EtapaDoEstagio[];
  /** Já em ordem de urgência: alerta, aviso, prazo mais curto. */
  readonly cartoes: readonly CartaoTorre[];
}

export interface TorreResponse {
  readonly hoje: string;
  readonly estagios: readonly EstagioDaTorre[];
  readonly saidas: { readonly encerradas: number; readonly descartadas: number };
}
