/**
 * O relatório da licitação — ver `apps/licitacoes/relatorio.py`. Só os
 * itens em que a empresa participou; as propostas de todos os participantes
 * vêm da Sentinela (Compras.gov.br). Valores em texto decimal ("825.04").
 */

export interface PropostaDoRelatorio {
  readonly classificacao: number | null;
  readonly fornecedor: string;
  readonly cnpj: string;
  readonly uf: string;
  readonly marca: string;
  readonly modelo: string;
  readonly valor: string | null;
  /** SituacaoPropostaItemEnum: 1/2/9 desclassificada, 3 aceita, 4 habilitado,
   * 5 inabilitado, 6 adjudicada; vazio = sem decisão. */
  readonly situacao: string;
  /** Desclassificada ou inabilitada. */
  readonly caiu: boolean;
  readonly da_empresa: boolean;
  /** Valor fora do padrão (mais de 5× ou menos de 1/5 da mediana). */
  readonly atipica: boolean;
}

export interface ItemDoRelatorio {
  readonly numero: string;
  readonly descricao: string;
  readonly quantidade: string | null;
  readonly participantes: number;
  readonly lido_em: string | null;
  readonly homologado: boolean;
  /** Nulo = ainda não decidido. */
  readonly empresa_venceu: boolean | null;
  /** Homologado: quem ganhou. Antes disso: quem está em 1º. */
  readonly vencedor: PropostaDoRelatorio | null;
  readonly empresa: {
    readonly classificacao: number | null;
    readonly posicao_efetiva: number | null;
    readonly marca: string;
    readonly modelo: string;
    readonly valor: string | null;
  };
  /** Valor da empresa − valor do vencedor (positivo = a empresa ficou acima). */
  readonly diferenca: string | null;
  readonly diferenca_percentual: string | null;
  readonly mediana: string | null;
  readonly marcas: readonly { readonly marca: string; readonly propostas: number }[];
  readonly propostas: readonly PropostaDoRelatorio[];
}

export interface RelatorioResponse {
  readonly id: number;
  readonly compra: string;
  readonly orgao_nome: string;
  readonly uasg: string;
  readonly objeto: string;
  readonly itens: readonly ItemDoRelatorio[];
  readonly resumo: {
    readonly itens: number;
    readonly com_propostas: number;
    readonly ganhos: number;
    readonly perdidos: number;
  };
}

/** O que quem abre o relatório já sabe (para o título aparecer na hora). */
export interface RelatorioCabecalho {
  readonly id: number;
  readonly titulo: string;
}
