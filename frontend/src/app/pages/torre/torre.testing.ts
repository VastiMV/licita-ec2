import { CartaoTorre, TorreResponse } from '../../contracts/licitacoes/torre.contracts';

/** Pregão 61/2026, IF Farroupilha: item 22 em 1º, aguardando julgamento. */
export const FARROUPILHA: CartaoTorre = {
  id: 61,
  estagio: 'disputar',
  etapa: 'aguardando_julgamento',
  etapa_rotulo: 'Aguardando julgamento',
  uasg: '158127',
  compra: 'Pregão 61/2026',
  orgao_nome: 'INST.FEDERAL DE EDUC.,CIENC.E TEC.FARROUPILHA',
  municipio: 'Santa Maria',
  uf: 'RS',
  objeto: 'Aquisição de semoventes e equipamentos de montaria.',
  data_encerramento_proposta: '2026-11-03',
  valor_total_estimado: null,
  link_plataforma:
    'https://cnetmobile.estaleiro.serpro.gov.br/comprasnet-web/public/compras/acompanhamento-compra?compra=15812705000612026',
  cotacao_id: null,
  salva: null,
  itens: [
    {
      numero: '22',
      descricao: 'Animal Vivo',
      etapa: 'aguardando_julgamento',
      etapa_rotulo: 'Aguardando julgamento',
      situacao: '',
      classificacao: 1,
      perdendo: false,
      perdido: '',
      quantidade: '20.0000',
      valor_unitario: '11999.0000',
      valor_total: '239980.00',
    },
  ],
  valor_ganho: '239980.00',
  etiquetas: [{ nivel: 'alerta', texto: 'convocação em andamento' }],
};

/** Pregão 56/2026, PM-DF: item 22 habilitado; itens 6 e 9 perdendo. */
export const PMDF: CartaoTorre = {
  ...FARROUPILHA,
  id: 56,
  etapa: 'aguardando_adjudicacao',
  etapa_rotulo: 'Aguardando adjudicação',
  uasg: '926670',
  compra: 'Pregão 56/2026',
  orgao_nome: 'DEPTO. SAÚDE E ASSIST AO PESSOAL POL MIL - DF',
  municipio: 'Brasília',
  uf: 'DF',
  itens: [
    {
      ...FARROUPILHA.itens[0],
      numero: '6',
      classificacao: 4,
      perdendo: true,
      valor_total: '13750.00',
    },
    {
      ...FARROUPILHA.itens[0],
      numero: '9',
      classificacao: 13,
      perdendo: true,
      valor_total: '95000.00',
    },
    {
      ...FARROUPILHA.itens[0],
      numero: '22',
      etapa: 'aguardando_adjudicacao',
      situacao: 'Fornecedor habilitado',
      valor_total: '15500.00',
    },
  ],
  valor_ganho: '15500.00',
  etiquetas: [],
};

/** Salva com cotação, ainda em Preparar: abre o Cotador. */
export const COTADA: CartaoTorre = {
  ...FARROUPILHA,
  id: 7,
  estagio: 'preparar',
  etapa: 'cotacao',
  etapa_rotulo: 'Cotação',
  orgao_nome: '',
  objeto: 'Papel A4 75 g/m²',
  data_encerramento_proposta: '2026-11-17',
  link_plataforma: '',
  cotacao_id: 15,
  salva: { id: 7, itens: [{ numero_item: 1 }] } as unknown as CartaoTorre['salva'],
  itens: [],
  valor_ganho: null,
  etiquetas: [],
};

export function torre(): TorreResponse {
  return {
    hoje: '2026-11-07',
    estagios: [
      {
        chave: 'preparar',
        rotulo: 'Preparar',
        total: 1,
        etapas: [
          { chave: 'oportunidade', rotulo: 'Oportunidade', total: 0 },
          { chave: 'cotacao', rotulo: 'Cotação', total: 1 },
          { chave: 'cadastro_proposta', rotulo: 'Cadastro de proposta', total: 0 },
        ],
        cartoes: [COTADA],
      },
      {
        chave: 'disputar',
        rotulo: 'Disputar',
        total: 2,
        etapas: [
          { chave: 'disputa', rotulo: 'Disputa', total: 0 },
          { chave: 'aguardando_julgamento', rotulo: 'Aguardando julgamento', total: 1 },
          { chave: 'julgado_habilitado', rotulo: 'Julgado e habilitado', total: 0 },
          { chave: 'aguardando_adjudicacao', rotulo: 'Aguardando adjudicação', total: 1 },
          { chave: 'homologado', rotulo: 'Homologado', total: 0 },
        ],
        cartoes: [FARROUPILHA, PMDF],
      },
      {
        chave: 'contratar',
        rotulo: 'Contratar',
        total: 0,
        etapas: [
          { chave: 'contrato', rotulo: 'Contrato', total: 0 },
          { chave: 'empenho', rotulo: 'Empenho / Ordem de Fornecimento', total: 0 },
        ],
        cartoes: [],
      },
      {
        chave: 'receber',
        rotulo: 'Receber',
        total: 0,
        etapas: [
          { chave: 'entrega', rotulo: 'Entrega', total: 0 },
          { chave: 'liquidado', rotulo: 'Liquidado', total: 0 },
          { chave: 'recebido', rotulo: 'Recebido', total: 0 },
        ],
        cartoes: [],
      },
    ],
    saidas: { encerradas: 3, descartadas: 8 },
  };
}
