import {
  CartaoTorre,
  EstagioTorre,
  EtapaTorre,
  ItemTorre,
} from '../../contracts/licitacoes/torre.contracts';
import { formatarMoeda, normalizarTitulo } from '../oportunidades/edital-card/edital-card.utils';

/** Oportunidade e Cotação já têm lista própria (Salvas e Cotador); as outras
 * etapas abrem a lista da Torre. */
export function rotaDaEtapa(etapa: EtapaTorre): string {
  if (etapa === 'oportunidade') return '/oportunidades/salvas';
  if (etapa === 'cotacao') return '/ciclo/cotador';
  return `/torre/etapa/${etapa}`;
}

export function rotaDoEstagio(estagio: EstagioTorre): string {
  return `/torre/estagio/${estagio}`;
}

/** Os valores chegam como texto decimal ("15500.00"). O espaço depois de
 * "R$" não quebra: o valor nunca fica com o "R$" numa linha e o número na
 * outra. */
export function moeda(valor: string | null | undefined): string | null {
  if (valor == null || valor === '') return null;
  return formatarMoeda(Number(valor))?.replace('R$ ', 'R$\u00a0') ?? null;
}

/** "UASG 158127 · Santa Maria/RS". */
export function localDoCartao(cartao: CartaoTorre): string {
  const cidade = [cartao.municipio, cartao.uf].filter(Boolean).join('/');
  return [cartao.uasg && `UASG ${cartao.uasg}`, cidade].filter(Boolean).join(' · ');
}

/** O nome do órgão em caixa de leitura; sem nome, o objeto faz as vezes. */
export function orgaoDoCartao(cartao: CartaoTorre): string {
  return normalizarTitulo(cartao.orgao_nome || cartao.objeto);
}

/** "Item 22 · 1º · Fornecedor habilitado · R$ 15.500,00" — o que importa
 * de um item, numa linha. */
export function resumoDoItem(item: ItemTorre): string {
  const posicao = item.classificacao ? `${item.classificacao}º` : '';
  const situacao = item.perdido
    ? `perdido: ${item.perdido}`
    : item.perdendo
      ? 'perdendo'
      : item.situacao || item.etapa_rotulo;
  return [`Item ${item.numero}`, posicao, situacao, moeda(item.valor_total)]
    .filter(Boolean)
    .join(' · ');
}

/** O nível do cartão é o da etiqueta mais grave. */
export function nivelDoCartao(cartao: CartaoTorre): 'alerta' | 'aviso' | 'neutro' {
  const niveis = new Set(cartao.etiquetas.map((e) => e.nivel));
  if (niveis.has('alerta')) return 'alerta';
  if (niveis.has('aviso')) return 'aviso';
  return 'neutro';
}
