/** O sino do Licita — ver `apps/notificacoes` no backend (09/11/2026). */

export type TipoNotificacao =
  | 'convocacao'
  | 'desconto'
  | 'recurso'
  | 'data'
  | 'situacao'
  | 'favorito'
  | 'resultado'
  | 'relatorio';

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

export interface NotificacoesResponse {
  readonly nao_lidas: number;
  readonly itens: readonly Notificacao[];
}
