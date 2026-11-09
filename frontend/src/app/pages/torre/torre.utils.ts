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
    : item.sinal === 'proximo'
      ? 'próximo a ser chamado'
      : item.perdendo
        ? 'perdendo'
        : item.situacao || item.etapa_rotulo;
  return [`Item ${item.numero}`, posicao, situacao, moeda(item.valor_total)]
    .filter(Boolean)
    .join(' · ');
}

/** 👍 / 🟠 / 👎 ao lado do item (pedido de 08/11/2026). O texto vai para
 * leitor de tela e para a dica. */
export function sinalDoItem(item: ItemTorre): { icone: string; texto: string } | null {
  switch (item.sinal) {
    case 'ganhando':
      return { icone: '👍', texto: 'Ganhando (1º lugar)' };
    case 'proximo':
      return { icone: '🟠', texto: 'Próximo a ser chamado' };
    case 'perdendo':
      return { icone: '👎', texto: item.perdido ? `Perdeu: ${item.perdido}` : 'Perdendo' };
    default:
      return null;
  }
}

/** "👍 ganhando 1 de 8" — no cartão, quando há itens com posição. Sem
 * nenhum item em 1º, o polegar é para baixo (08/11/2026). */
export function ganhandoDoCartao(cartao: CartaoTorre): string | null {
  if (!cartao.itens_com_posicao) return null;
  const icone = cartao.itens_ganhando > 0 ? '👍' : '👎';
  return `${icone} ganhando ${cartao.itens_ganhando} de ${cartao.itens_com_posicao}`;
}

/** O relatório faz sentido do Disputar em diante (já há propostas). */
export function temRelatorio(cartao: CartaoTorre): boolean {
  return cartao.estagio !== 'preparar' && cartao.itens.length > 0;
}

/** O nível do cartão é o da etiqueta mais grave. */
export function nivelDoCartao(cartao: CartaoTorre): 'alerta' | 'aviso' | 'neutro' {
  const niveis = new Set(cartao.etiquetas.map((e) => e.nivel));
  if (niveis.has('alerta')) return 'alerta';
  if (niveis.has('aviso')) return 'aviso';
  return 'neutro';
}

/** O nome curto de cada etapa, para a trilha do cartão. */
const ETAPAS_DO_ESTAGIO: Record<EstagioTorre, readonly (readonly [EtapaTorre, string])[]> = {
  preparar: [
    ['oportunidade', 'Oportunidade'],
    ['cotacao', 'Cotação'],
    ['cadastro_proposta', 'Cadastro de proposta'],
  ],
  disputar: [
    ['disputa', 'Disputa'],
    ['aguardando_julgamento', 'Aguardando julgamento'],
    ['julgado_habilitado', 'Aceita e habilitada'],
    ['aguardando_adjudicacao', 'Habilitada (aguardando adjudicação)'],
  ],
  contratar: [
    ['homologado', 'Homologado'],
    ['contrato', 'Contrato'],
    ['empenho', 'Empenho / OF'],
  ],
  receber: [
    ['entrega', 'Entrega'],
    ['liquidado', 'Liquidado'],
    ['recebido', 'Recebido'],
  ],
};

/** A trilha do cartão: a etapa de agora e as que faltam no estágio
 * ("● Aguardando julgamento › Aceita e habilitada › …") — o que vem depois,
 * sem precisar lembrar. */
export function trilhaDoCartao(cartao: CartaoTorre): { rotulo: string; atual: boolean }[] {
  const etapas = ETAPAS_DO_ESTAGIO[cartao.estagio];
  const daqui = etapas.findIndex(([chave]) => chave === cartao.etapa);
  return etapas.slice(Math.max(daqui, 0)).map(([chave, rotulo]) => ({
    rotulo,
    atual: chave === cartao.etapa,
  }));
}

/** Os itens que ainda contam (perdidos saem). */
function itensVivos(cartao: CartaoTorre): ItemTorre[] {
  return cartao.itens.filter((item) => !item.perdido);
}

/** O item em que a empresa está à frente, quando é um só. */
function itemPrincipal(cartao: CartaoTorre): ItemTorre | null {
  const vivos = itensVivos(cartao);
  const frente = vivos.filter((item) => !item.perdendo);
  if (vivos.length === 1) return vivos[0];
  return frente.length === 1 ? frente[0] : null;
}

/** "Pregão 61/2026 · item 22". */
export function compraDoCartao(cartao: CartaoTorre): string {
  const item = itemPrincipal(cartao);
  return [cartao.compra, item && `item ${item.numero}`].filter(Boolean).join(' · ');
}

function numero(valor: string | null): string | null {
  if (valor == null || valor === '') return null;
  return Number(valor).toLocaleString('pt-BR', { maximumFractionDigits: 4 });
}

/** "1º lugar · 20 × R$ 11.999,00 = R$ 239.980,00", ou "17 itens · R$ 53.312,08". */
export function linhaDoCartao(cartao: CartaoTorre): string | null {
  const vivos = itensVivos(cartao);
  if (!vivos.length) return null;
  const item = itemPrincipal(cartao);
  if (item && vivos.length === 1) {
    const lugar = item.classificacao ? `${item.classificacao}º lugar` : '';
    const qtd = numero(item.quantidade);
    const unitario = moeda(item.valor_unitario);
    const conta =
      qtd && unitario
        ? `${qtd} × ${unitario} = ${moeda(item.valor_total)}`
        : moeda(item.valor_total);
    return [lugar, conta].filter(Boolean).join(' · ');
  }
  const frente = vivos.filter((i) => !i.perdendo).length;
  return [`${frente || vivos.length} ${frente === 1 ? 'item' : 'itens'}`, moeda(cartao.valor_ganho)]
    .filter(Boolean)
    .join(' · ');
}

/** "🟠 1 próximo a ser chamado · 👎 3 perdendo" — embaixo da linha. Só o
 * próximo de verdade é 🟠 (09/11/2026): quem está em 23º enquanto analisam o
 * 2º não "pode ser chamado" agora. */
export function perdendoDoCartao(cartao: CartaoTorre): string | null {
  const vivos = itensVivos(cartao);
  const proximos = vivos.filter((item) => item.sinal === 'proximo').length;
  const perdendo = vivos.filter((item) => item.perdendo && item.sinal !== 'proximo').length;
  const partes: string[] = [];
  if (proximos) {
    partes.push(
      `🟠 ${proximos} ${proximos === 1 ? 'próximo' : 'próximos'} a ser chamado${proximos === 1 ? '' : 's'}`,
    );
  }
  if (perdendo) partes.push(`👎 ${perdendo} perdendo`);
  return partes.length ? partes.join(' · ') : null;
}

/** "Proposta até 10/11" — só em Preparar. Aviso quando faltam 3 dias ou menos. */
export function prazoDoCartao(
  cartao: CartaoTorre,
  hoje: Date = new Date(),
): { texto: string; urgente: boolean } | null {
  const data = cartao.data_encerramento_proposta;
  if (cartao.estagio !== 'preparar' || !data) return null;
  const [ano, mes, dia] = data.split('-').map(Number);
  const prazo = new Date(ano, mes - 1, dia);
  const inicioDeHoje = new Date(hoje.getFullYear(), hoje.getMonth(), hoje.getDate());
  const dias = Math.round((prazo.getTime() - inicioDeHoje.getTime()) / 86_400_000);
  const ddmm = `${String(dia).padStart(2, '0')}/${String(mes).padStart(2, '0')}`;
  return { texto: `Proposta até ${ddmm}`, urgente: dias <= 3 };
}
