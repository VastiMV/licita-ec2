/**
 * A lógica do modal do processo, separada do template: o estado de cada
 * fase, os nós da linha do tempo (salvamentos da cotação agrupados) e a
 * narração da fase selecionada. Desenho: `docs/design/modal-processo/`.
 */

import {
  DesfechoProcesso,
  ProcessoCabecalho,
  EtapaCiclo,
  EventoDoProcesso,
  ProcessoResponse,
  TipoDesfecho,
} from '../../../../contracts/licitacoes/encerrada.contracts';

export const ETAPAS: readonly { id: EtapaCiclo; nome: string }[] = [
  { id: 'oportunidade', nome: 'Oportunidade' },
  { id: 'cotacao', nome: 'Cotação' },
  { id: 'proposta', nome: 'Proposta' },
  { id: 'disputa', nome: 'Disputa' },
  { id: 'empenho', nome: 'Empenho' },
];

/** Família de cor: neutro (descarte), alerta (prazo), perigo (perdeu),
 * sucesso (concluiu). */
export type Familia = 'neutro' | 'alerta' | 'perigo' | 'sucesso';
export type IconeDesfecho = 'lixeira' | 'relogio' | 'x' | 'check';

export const DESFECHOS: Record<
  TipoDesfecho,
  { familia: Familia; nome: string; curto: string; icone: IconeDesfecho }
> = {
  descartada: { familia: 'neutro', nome: 'Descartado', curto: 'Descartado', icone: 'lixeira' },
  prazo_oportunidade: {
    familia: 'alerta',
    nome: 'Prazo perdido sem cotação',
    curto: 'Prazo perdido',
    icone: 'relogio',
  },
  prazo_cotacao: {
    familia: 'alerta',
    nome: 'Prazo perdido na cotação',
    curto: 'Prazo perdido',
    icone: 'relogio',
  },
  desclassificada: {
    familia: 'perigo',
    nome: 'Proposta desclassificada',
    curto: 'Desclassificada',
    icone: 'x',
  },
  perdido_disputa: {
    familia: 'perigo',
    nome: 'Não venceu na disputa',
    curto: 'Não venceu',
    icone: 'x',
  },
  falhou_empenho: {
    familia: 'perigo',
    nome: 'Falhou no empenho',
    curto: 'Empenho falhou',
    icone: 'x',
  },
  concluido: { familia: 'sucesso', nome: 'Concluído', curto: 'Concluído', icone: 'check' },
  descartada_manual: {
    familia: 'neutro',
    nome: 'Descartada manualmente',
    curto: 'Descartada',
    icone: 'lixeira',
  },
  sem_proposta: {
    familia: 'alerta',
    nome: 'Sem proposta cadastrada',
    curto: 'Sem proposta',
    icone: 'x',
  },
  perdida: { familia: 'perigo', nome: 'Perdida', curto: 'Perdida', icone: 'x' },
  acompanhando: {
    familia: 'neutro',
    nome: 'Acompanhando o resultado',
    curto: 'Acompanhando',
    icone: 'relogio',
  },
  revogada: { familia: 'alerta', nome: 'Revogada pelo órgão', curto: 'Revogada', icone: 'x' },
  anulada: { familia: 'alerta', nome: 'Anulada pelo órgão', curto: 'Anulada', icone: 'x' },
  fracassada: { familia: 'alerta', nome: 'Fracassada', curto: 'Fracassada', icone: 'x' },
  deserta: { familia: 'alerta', nome: 'Deserta', curto: 'Deserta', icone: 'x' },
};

// ---------- formatação ----------

export function brl(valor: number): string {
  return valor.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

/** Aceita data (`aaaa-mm-dd`, sem fuso) ou data e hora ISO. */
function comoData(iso: string): Date {
  return iso.length === 10 ? new Date(`${iso}T00:00:00`) : new Date(iso);
}

export function dia(iso: string): string {
  return comoData(iso).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
}

export function diaAno(iso: string): string {
  return comoData(iso).toLocaleDateString('pt-BR');
}

export function hora(iso: string): string {
  return comoData(iso).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
}

export function diaHora(iso: string): string {
  return iso.length === 10 ? dia(iso) : `${dia(iso)}, ${hora(iso)}`;
}

export function diasEntre(de: string, ate: string | Date): number {
  const a = comoData(de);
  const b = typeof ate === 'string' ? comoData(ate) : ate;
  const meiaNoite = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  return Math.round((meiaNoite(b) - meiaNoite(a)) / 86_400_000);
}

export function nDias(n: number): string {
  return `${n} ${n === 1 ? 'dia' : 'dias'}`;
}

export function iniciais(nome: string): string {
  return nome
    .split(/[\s@.]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((parte) => parte[0].toUpperCase())
    .join('');
}

function unicos(lista: readonly (string | null)[]): string[] {
  return [...new Set(lista.filter((x): x is string => !!x))];
}

function emLista(itens: readonly string[]): string {
  return itens.length < 2 ? itens.join('') : `${itens.slice(0, -1).join(', ')} e ${itens.at(-1)}`;
}

// ---------- fases ----------

export type ClasseFase = 'feita' | 'pulada' | 'parou' | 'concluiu' | 'depois';

export interface EstadoFase {
  readonly classe: ClasseFase;
  readonly sub: string;
  readonly rotulo: string;
  readonly familia: Familia | null;
}

export function eventosDa(processo: ProcessoResponse, etapa: EtapaCiclo): EventoDoProcesso[] {
  return processo.eventos.filter((e) => e.etapa === etapa);
}

function indiceDa(etapa: EtapaCiclo): number {
  return ETAPAS.findIndex((e) => e.id === etapa);
}

export function indiceAtual(processo: ProcessoResponse): number {
  return indiceDa(processo.etapa);
}

export function estadoDaFase(processo: ProcessoResponse, i: number): EstadoFase {
  const atual = indiceAtual(processo);
  const eventos = eventosDa(processo, ETAPAS[i].id);
  const desfecho = processo.desfecho;
  if (i < atual) {
    return eventos.length
      ? { classe: 'feita', sub: dia(eventos[0].data), rotulo: 'Concluída', familia: null }
      : { classe: 'pulada', sub: 'sem registro', rotulo: 'Sem registro', familia: null };
  }
  if (i === atual) {
    if (!desfecho) {
      return {
        classe: 'parou',
        sub: eventos.length ? `desde ${dia(eventos[0].data)}` : 'em andamento',
        rotulo: 'Em andamento',
        familia: null,
      };
    }
    const d = DESFECHOS[desfecho.tipo];
    return desfecho.tipo === 'concluido'
      ? {
          classe: 'concluiu',
          sub: `Concluído · ${dia(desfecho.data)}`,
          rotulo: 'Concluída',
          familia: 'sucesso',
        }
      : {
          classe: 'parou',
          sub: `${d.curto} · ${dia(desfecho.data)}`,
          rotulo: 'Parou aqui',
          familia: d.familia,
        };
  }
  return { classe: 'depois', sub: 'não alcançada', rotulo: 'Não alcançada', familia: null };
}

// ---------- linha do tempo ----------

/** Um evento, ou um bloco de salvamentos intermediários da cotação. */
export type NoLinhaDoTempo =
  | { readonly tipo: 'evento'; readonly evento: EventoDoProcesso }
  | {
      readonly tipo: 'grupo';
      readonly eventos: readonly EventoDoProcesso[];
      readonly autores: readonly string[];
    };

export interface GrupoDaEtapa {
  readonly indice: number;
  readonly etapa: EtapaCiclo;
  readonly nome: string;
  readonly periodo: string;
  readonly total: number;
  readonly estado: EstadoFase;
  readonly nos: readonly NoLinhaDoTempo[];
}

/** A partir de quantas atualizações seguidas elas viram um bloco. */
const MINIMO_PARA_AGRUPAR = 3;

export function nosDaEtapa(eventos: readonly EventoDoProcesso[]): NoLinhaDoTempo[] {
  const nos: NoLinhaDoTempo[] = [];
  for (let i = 0; i < eventos.length;) {
    if (eventos[i].tipo !== 'cotacao_atualizada') {
      nos.push({ tipo: 'evento', evento: eventos[i++] });
      continue;
    }
    let fim = i;
    while (fim < eventos.length && eventos[fim].tipo === 'cotacao_atualizada') fim++;
    const seguidos = eventos.slice(i, fim);
    if (seguidos.length >= MINIMO_PARA_AGRUPAR) {
      const ultimo = seguidos.pop()!;
      nos.push({ tipo: 'grupo', eventos: seguidos, autores: unicos(seguidos.map((e) => e.autor)) });
      nos.push({ tipo: 'evento', evento: { ...ultimo, texto: 'Última atualização da cotação' } });
    } else {
      seguidos.forEach((evento) => nos.push({ tipo: 'evento', evento }));
    }
    i = fim;
  }
  return nos;
}

export function periodo(eventos: readonly EventoDoProcesso[]): string {
  if (!eventos.length) return '';
  const inicio = dia(eventos[0].data);
  const fim = dia(eventos[eventos.length - 1].data);
  const quantos = `${eventos.length} ${eventos.length === 1 ? 'evento' : 'eventos'}`;
  return `${inicio === fim ? inicio : `${inicio} – ${fim}`} · ${quantos}`;
}

/** As etapas que têm o que contar (até a atual). */
export function gruposDaLinhaDoTempo(processo: ProcessoResponse): GrupoDaEtapa[] {
  return ETAPAS.slice(0, indiceAtual(processo) + 1).map((etapa, indice) => {
    const eventos = eventosDa(processo, etapa.id);
    return {
      indice,
      etapa: etapa.id,
      nome: etapa.nome,
      periodo: periodo(eventos),
      total: eventos.length,
      estado: estadoDaFase(processo, indice),
      nos: nosDaEtapa(eventos),
    };
  });
}

/** Pontos de um mini-gráfico (0–1 nos dois eixos) da evolução do valor. */
export function tendencia(eventos: readonly EventoDoProcesso[]): string {
  const valores = eventos.map((e) => e.valor).filter((v): v is number => v !== null);
  if (valores.length < 2) return '';
  const min = Math.min(...valores);
  const amplitude = Math.max(...valores) - min || 1;
  return valores
    .map((v, i) => `${(i / (valores.length - 1)) * 100},${30 - ((v - min) / amplitude) * 28}`)
    .join(' ');
}

// ---------- narração da fase ----------

export interface Narracao {
  readonly pontos: readonly string[];
  readonly porque: string | null;
  readonly familia: Familia | null;
}

/** Os pontos são HTML simples (`<b>`) — o texto vem dos nossos próprios
 * dados, mas nomes passam por `escapar` mesmo assim. */
function escapar(texto: string): string {
  return texto.replace(
    /[&<>"]/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]!,
  );
}

export function narrar(
  processo: ProcessoResponse,
  cabecalho: ProcessoCabecalho,
  i: number,
): Narracao {
  const etapa = ETAPAS[i];
  const eventos = eventosDa(processo, etapa.id);
  const estado = estadoDaFase(processo, i);
  const desfecho = processo.desfecho;
  const pontos: string[] = [];
  const achar = (tipo: string) => eventos.find((e) => e.tipo === tipo);
  const proxima = ETAPAS[i + 1] ? eventosDa(processo, ETAPAS[i + 1].id)[0] : undefined;
  const prazo = cabecalho.data_encerramento_proposta;

  if (estado.classe === 'depois') {
    const ondeParou = ETAPAS[indiceAtual(processo)].nome;
    pontos.push('Etapa não alcançada.');
    if (desfecho) {
      pontos.push(
        `O processo encerrou em <b>${ondeParou}</b> — ` +
          `${DESFECHOS[desfecho.tipo].nome.toLowerCase()}, em ${diaAno(desfecho.data)}.`,
      );
    }
    return { pontos, porque: null, familia: null };
  }
  if (estado.classe === 'pulada') {
    return {
      pontos: [
        'Nenhum registro nesta etapa.',
        'O processo seguiu direto para a etapa seguinte — o sistema avisa, mas não trava.',
      ],
      porque: null,
      familia: null,
    };
  }

  if (etapa.id === 'oportunidade') {
    const salva = achar('oportunidade_salva');
    const removida = achar('removida');
    const venceu = achar('prazo_encerrado');
    if (salva) {
      const quem = salva.autor ? ` por <b>${escapar(salva.autor)}</b>` : '';
      pontos.push(`Edital salvo${quem} em ${diaHora(salva.data)}.`);
      if (prazo) {
        pontos.push(
          `Prazo da proposta: <b>${diaAno(prazo)}</b> — ${nDias(diasEntre(salva.data, prazo))} depois de salvo.`,
        );
      }
    }
    if (removida) {
      const depois = salva ? `, ${nDias(diasEntre(salva.data, removida.data))} depois` : '';
      pontos.push(
        `Removido da lista por <b>${escapar(removida.autor ?? 'alguém')}</b> em ` +
          `${diaHora(removida.data)}${depois}. Motivo não informado.`,
      );
    }
    if (venceu && salva) {
      pontos.push(
        `Ficou ${nDias(diasEntre(salva.data, venceu.data))} sem cotação até o prazo vencer.`,
      );
    }
    if (proxima) {
      const dias = salva ? diasEntre(salva.data, proxima.data) : 0;
      pontos.push(
        `Seguiu para Cotação em ${dia(proxima.data)}${dias ? `, ${nDias(dias)} depois.` : ', no mesmo dia.'}`,
      );
    }
  }

  if (etapa.id === 'cotacao') {
    const cotacoes = eventos.filter((e) => e.tipo.startsWith('cotacao_'));
    const primeira = cotacoes[0];
    const ultima = cotacoes.at(-1);
    if (primeira && ultima) {
      const quem = primeira.autor ? ` por <b>${escapar(primeira.autor)}</b>` : '';
      const valor = primeira.valor !== null ? ` com ${brl(primeira.valor)}` : '';
      pontos.push(`Cotação criada${quem} em ${diaHora(primeira.data)}${valor}.`);
      if (cotacoes.length > 1) {
        const autores = emLista(unicos(cotacoes.map((e) => e.autor)).map(escapar));
        pontos.push(
          `<b>${cotacoes.length} salvamentos</b> em ${nDias(diasEntre(primeira.data, ultima.data) + 1)}` +
            `${autores ? `, por ${autores}` : ''}.`,
        );
      }
      if (ultima.valor !== null) {
        const estimado = cabecalho.valor_total_estimado;
        const fracao = estimado
          ? ` — ${Math.round((ultima.valor / estimado) * 100)}% do estimado`
          : '';
        pontos.push(
          `Valor final <b>${brl(ultima.valor)}</b>${fracao}, em ${diaHora(ultima.data)}.`,
        );
      }
      const venceu = achar('prazo_encerrado');
      if (venceu) {
        pontos.push(
          `Prazo venceu ${nDias(diasEntre(ultima.data, venceu.data))} após a última edição, sem proposta.`,
        );
      }
    }
    if (proxima) pontos.push(`Virou proposta em ${dia(proxima.data)}.`);
  }

  if (etapa.id !== 'oportunidade' && etapa.id !== 'cotacao') {
    eventos.forEach((e) =>
      pontos.push(
        `${escapar(e.texto)} em ${diaHora(e.data)}` +
          `${e.autor ? ` por <b>${escapar(e.autor)}</b>` : ' (sistema)'}` +
          `${e.valor !== null ? `: ${brl(e.valor)}` : ''}.`,
      ),
    );
  }

  const encerrouAqui = estado.classe === 'parou' || estado.classe === 'concluiu';
  return {
    pontos,
    porque: encerrouAqui && desfecho ? desfecho.porque : null,
    familia: estado.familia,
  };
}

export function textoDoDesfecho(desfecho: DesfechoProcesso): string {
  return desfecho.tipo === 'concluido'
    ? 'Concluído — empenhado e entregue'
    : DESFECHOS[desfecho.tipo].nome;
}
