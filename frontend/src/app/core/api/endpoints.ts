/**
 * Caminhos da API, centralizados. Nenhum serviço de domínio escreve uma
 * string de rota solta — todos importam daqui, então mudar uma rota no
 * backend é uma mudança num só lugar no frontend.
 */
export const ENDPOINTS = {
  auth: {
    login: 'auth/login/',
    refresh: 'auth/refresh/',
    logout: 'auth/logout/',
  },
  /** O vigia da Sentinela (extensão do Chrome), para o botão do topo. */
  /** O sino: últimas notificações e "marcar como lidas". */
  notificacoes: {
    lista: 'notificacoes/',
    lidas: 'notificacoes/lidas/',
  },
  sentinela: {
    estado: 'sentinela/estado/',
  },
  licitacoes: {
    oportunidades: 'licitacoes/oportunidades/',
    compraDetalhe: (cnpj: string, ano: string | number, sequencial: string | number) =>
      `licitacoes/compras/${cnpj}/${ano}/${sequencial}/detalhe/`,
    /** O quadro do Ciclo de Licitação, com a etapa já calculada. */
    ciclo: 'licitacoes/ciclo/',
    /** A Torre de Controle: 4 estágios, a etapa calculada por item. */
    torre: 'licitacoes/torre/',
    salvas: 'licitacoes/salvas/',
    salvasChaves: 'licitacoes/salvas/chaves/',
    /** A lista do Cotador: as salvas na etapa Cotação. */
    cotacoes: 'licitacoes/cotacoes/',
    /** Quem saiu do ciclo — encerramento calculado no backend. */
    encerradas: 'licitacoes/encerradas/',
    /** Tiradas da lista antes do prazo — tela própria, fora de Encerradas. */
    descartadas: 'licitacoes/descartadas/',
    salva: (id: number) => `licitacoes/salvas/${id}/`,
    /** A lixeira da Torre: GET a pergunta, POST descarta. */
    salvaDescartar: (id: number) => `licitacoes/salvas/${id}/descartar/`,
    /** Histórico cru de uma salva (o log). */
    salvaEventos: (id: number) => `licitacoes/salvas/${id}/eventos/`,
    /** A história no formato do modal do processo: etapa de cada evento,
     * valores e o desfecho. */
    processo: (id: number) => `licitacoes/salvas/${id}/processo/`,
    /** O relatório da licitação: vencedor, marca e diferença, item a item. */
    relatorio: (id: number) => `licitacoes/salvas/${id}/relatorio/`,
    /** O relatório do mês (participou, ganhou, perdeu, faturamento, lucro). */
    relatorioMensal: 'licitacoes/relatorios/mensal/',
  },
  /** Fabricante › Marca › Modelo e a tabela de preços (`apps/produtos`). */
  produtos: {
    fabricantes: 'produtos/fabricantes/',
    fabricantesOpcoes: 'produtos/fabricantes/opcoes/',
    fabricante: (id: number) => `produtos/fabricantes/${id}/`,
    marcas: 'produtos/marcas/',
    marcasOpcoes: 'produtos/marcas/opcoes/',
    marca: (id: number) => `produtos/marcas/${id}/`,
    modelos: 'produtos/modelos/',
    modelosOpcoes: 'produtos/modelos/opcoes/',
    modelo: (id: number) => `produtos/modelos/${id}/`,
    precoSugerido: 'produtos/precos/sugerido/',
  },
  /** Onde os arquivos ficam (`apps/armazenamento`) — driver escolhido e
   * configurado pelo cliente, só por administrador. */
  armazenamento: {
    drivers: 'armazenamento/drivers/',
    config: 'armazenamento/config/',
    testar: 'armazenamento/testar/',
  },
  /** Quem acessa o produto (`apps/accounts`) — só o super usuário, menos
   * `perfil`. */
  usuarios: {
    lista: 'usuarios/',
    /** O próprio perfil — qualquer usuário logado. */
    perfil: 'usuarios/eu/',
    /** A própria foto: PUT `{foto: "data:image/jpeg;base64,…"}`, DELETE tira. */
    foto: 'usuarios/eu/foto/',
    detalhe: (id: number) => `usuarios/${id}/`,
  },
  /** O dossiê de habilitação da empresa (`apps/documentos`) — certidões,
   * contrato social, balanço. Não confundir com os documentos da
   * **licitação**, que são arquivo de uma fase do processo. */
  documentos: {
    lista: 'documentos/',
    tipos: 'documentos/tipos/',
    detalhe: (id: number) => `documentos/${id}/`,
    restaurar: (id: number) => `documentos/${id}/restaurar/`,
    versoes: (id: number) => `documentos/${id}/versoes/`,
    eventos: (id: number) => `documentos/${id}/eventos/`,
    download: (versaoId: number) => `documentos/versoes/${versaoId}/download/`,
  },
  /** Os CNPJs com que a equipe disputa (`apps/empresas`) — não confundir
   * com `fornecedores`, que é de quem a equipe compra. */
  empresas: {
    lista: 'empresas/',
    detalhe: (id: number) => `empresas/${id}/`,
    /** Cadastro enxuto — o seletor de "com qual CNPJ eu disputo". */
    opcoes: 'empresas/opcoes/',
  },
  fornecedores: {
    lista: 'fornecedores/',
    detalhe: (id: number) => `fornecedores/${id}/`,
    /** Cadastro inteiro, enxuto — o seletor de fornecedor do Cotador. */
    opcoes: 'fornecedores/opcoes/',
  },
  /** O Cotador (`apps/cotador`). */
  /** Propostas (`apps/propostas`): a lista, gerar, o Word e os arquivos. */
  propostas: {
    lista: 'propostas/',
    detalhe: (id: number) => `propostas/${id}/`,
    documento: (id: number) => `propostas/${id}/documento/`,
    pasta: (id: number) => `propostas/${id}/pasta/`,
    arquivos: (id: number) => `propostas/${id}/arquivos/`,
    arquivo: (id: number) => `propostas/arquivos/${id}/`,
    arquivoDownload: (id: number) => `propostas/arquivos/${id}/download/`,
    modelo: 'propostas/modelo/',
    modeloDownload: 'propostas/modelo/download/',
  },
  cotador: {
    cotacoes: 'cotador/cotacoes/',
    cotacao: (id: number) => `cotador/cotacoes/${id}/`,
    planilha: (id: number) => `cotador/cotacoes/${id}/planilha/`,
    /** A cotação de uma oportunidade salva — 404 quando ainda não foi
     * cotada, que é o sinal de abrir o modal em branco. */
    cotacaoDaOportunidade: (oportunidadeId: number) =>
      `cotador/oportunidades/${oportunidadeId}/cotacao/`,
  },
} as const;
