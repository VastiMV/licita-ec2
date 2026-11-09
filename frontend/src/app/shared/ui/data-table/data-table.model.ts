/**
 * Tipos do `DataTableComponent` — a tabela reutilizável do projeto
 * (inspirada no DataTables.net: busca, ordenação por qualquer coluna e
 * paginação, só que integrados ao endpoint em vez de a um array em memória).
 *
 * Uma coluna descreve **como extrair** o texto de uma linha (`valor`), não
 * o HTML dela: assim a tabela serve qualquer domínio sem conhecer nenhum.
 */

export type DirecaoOrdenacao = 'asc' | 'desc';

/** Realce de uma célula específica (ex.: prazo vencido em vermelho). */
export type TomCelula = 'alerta' | 'perigo' | 'sucesso';

export interface ColunaTabela<T> {
  /** Nome que vai no `ordering` do endpoint — contrato com o backend
   * (ver `ORDENACOES` em `apps/licitacoes/views.py`). */
  readonly chave: string;
  readonly titulo: string;
  /** Texto da célula. Formatação (data, moeda) acontece aqui, na página que
   * conhece o domínio — a tabela só imprime o que voltar. */
  readonly valor: (linha: T) => string;
  /** Padrão: ordenável. Só desligue onde o backend não sabe ordenar. */
  readonly ordenavel?: boolean;
  /** Alinha à direita e usa fonte tabular (valores, quantidades). */
  readonly numerica?: boolean;
  /** Proíbe a quebra de linha na célula — para coluna cujo valor só faz
   * sentido inteiro numa linha só (cidade, datas). Quem usa é responsável
   * por encurtar o texto, senão a coluna estica a tabela. */
  readonly umaLinha?: boolean;
  /** Segunda linha da célula, menor e apagada — o dado que qualifica o
   * principal sem virar coluna própria (o nome fantasia embaixo da razão
   * social). `null` = célula de uma linha só. */
  readonly secundario?: (linha: T) => string | null;
  /** Texto completo em `title` (tooltip do navegador) — é o par natural de
   * uma coluna que mostra o valor encurtado. */
  readonly dica?: (linha: T) => string | null;
  /** Destaque condicional da célula — `null` = célula normal. */
  readonly tom?: (linha: T) => TomCelula | null;
  /** Corta o texto em N linhas com "…" (o completo vai na `dica`). Para
   * texto longo que não pode aumentar a altura da linha (o objeto do edital). */
  readonly limiteLinhas?: number;
}

/** Tudo que o endpoint precisa saber para devolver a página certa. A tabela
 * não guarda esse estado: recebe pronto e devolve o próximo por `estadoMudou`
 * — quem chama o serviço é a página. */
export interface EstadoTabela {
  readonly pagina: number;
  readonly tamanhoPagina: number;
  /** `chave` da coluna ordenada. */
  readonly ordenarPor: string;
  readonly direcao: DirecaoOrdenacao;
  readonly busca: string;
}

export function estadoInicialTabela(parcial: Partial<EstadoTabela> = {}): EstadoTabela {
  return {
    pagina: 1,
    tamanhoPagina: 10,
    ordenarPor: '',
    direcao: 'asc',
    busca: '',
    ...parcial,
  };
}

/** Formato que a tabela espera do `ordering` do endpoint: `-coluna` para
 * descendente (mesma convenção do DRF). */
export function parametroOrdenacao(estado: EstadoTabela): string {
  if (!estado.ordenarPor) return '';
  return estado.direcao === 'desc' ? `-${estado.ordenarPor}` : estado.ordenarPor;
}
