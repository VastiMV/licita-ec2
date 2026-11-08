/** O estado da Sentinela — ver `apps/sentinela/estado.py` no backend. */
export type EstadoSentinela = 'nao_instalada' | 'ok' | 'precisa_de_voce' | 'parada';

export interface EstadoSentinelaResponse {
  readonly estado: EstadoSentinela;
  /** ISO 8601; nulo se nunca falou. */
  readonly ultimo_pulso: string | null;
  readonly ultima_captura: string | null;
  /** "A sessão do Compras.gov caiu", "Nenhuma aba do Compras.gov aberta"… */
  readonly detalhe: string;
}
