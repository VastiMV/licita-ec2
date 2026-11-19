/** O sino do Licita — ver `apps/notificacoes` no backend (09/11/2026). */

export type TipoNotificacao =
  | 'convocacao'
  | 'desconto'
  | 'recurso'
  | 'data'
  | 'situacao'
  | 'favorito'
  | 'resultado'
  | 'relatorio'
  | 'mensagem'
  /** A própria Sentinela parada ou sem ler (GEN-73, 14/11/2026). */
  | 'sentinela'
  /** Empenho, liquidação ou pagamento do Portal da Transparência (GEN-97, 18/11/2026). */
  | 'financeiro';

export interface Notificacao {
  readonly id: number;
  readonly tipo: TipoNotificacao;
  readonly nivel: 'alerta' | 'aviso' | 'info';
  readonly titulo: string;
  readonly texto: string;
  readonly oportunidade_id: number | null;
  readonly criada_em: string;
  readonly lida: boolean;
}

/**
 * O sino em duas partes (GEN-104, 19/11/2026): `precisa` (o que pede ação
 * dele: pregoeiro, convocação, desconto, recurso, compra suspensa/revogada)
 * e `para_saber` (o resto). `nao_lidas` conta só `precisa` (o número
 * vermelho).
 */
export interface NotificacoesResponse {
  readonly nao_lidas: number;
  readonly para_saber_nao_lidas: number;
  readonly precisa: readonly Notificacao[];
  readonly para_saber: readonly Notificacao[];
}
