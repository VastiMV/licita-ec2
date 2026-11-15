import {
  ALVOS_RAPIDOS,
  ItemCotador,
  OfertaCotador,
  PADROES_INICIAIS,
  PadroesCotador,
  calcularItem,
  custoUnitarioDa,
  formatarMoeda,
  formatarPercentual,
  melhorOferta,
  ofertaEscolhida,
  referenciaDe,
  tetoDoSlider,
  totalizar,
} from './cotador.model';

/** Os mesmos números de `apps/cotador/test_formulas.py`: se uma das duas
 * implementações derivar, este teste (ou o de lá) cai. Escritos aqui, e não
 * lidos de `PADROES_INICIAIS`, porque o padrão da tela pode mudar sem que a
 * conta mude — foi o que aconteceu quando o markup virou 12%–45%. */
const PADROES: PadroesCotador = {
  transporte: 8,
  garantia: 0,
  markupMinimo: 10,
  markupAlvo: 35,
  impostos: 10,
};

function oferta(parcial: Partial<OfertaCotador> = {}): OfertaCotador {
  return {
    id: parcial.id ?? 'o1',
    fornecedorId: null,
    nome: 'Distribuidora Sul',
    custoProduto: 24.9,
    frete: 1.2,
    outros: 0,
    ...parcial,
  };
}

function item(parcial: Partial<ItemCotador> = {}): ItemCotador {
  const ofertas = parcial.ofertas ?? [oferta()];
  return {
    id: 'i1',
    numeroItem: '1',
    descricao: 'Papel A4 75g — resma 500fl',
    unidade: 'RESMA',
    quantidade: 120,
    valorReferencia: 30,
    markupMinimo: null,
    markupAlvo: null,
    impostos: null,
    escolhida: ofertas[0]?.id ?? '',
    ...parcial,
    ofertas,
  };
}

const arredondar = (valor: number) => Math.round(valor * 100) / 100;

describe('preço de um item', () => {
  it('custo unitário soma produto, frete e outros', () => {
    expect(calcularItem(item(), PADROES).custoUnitario).toBeCloseTo(26.1, 10);
  });

  it('preço final embute transporte, markup e tributo', () => {
    // 26,10 × (1 + 8% + 35%) ÷ (1 − 10%) = 41,47
    expect(arredondar(calcularItem(item(), PADROES).precoFinalUnitario)).toBe(41.47);
  });

  it('preço de reserva usa o markup mínimo e fica abaixo do proposto', () => {
    // 26,10 × (1 + 8% + 10%) ÷ (1 − 10%) = 34,22
    const calculo = calcularItem(item(), PADROES);
    expect(arredondar(calculo.precoReservaUnitario)).toBe(34.22);
    expect(calculo.folgaUnitaria).toBeGreaterThan(0);
    expect(calculo.noLimite).toBe(false);
  });

  it('markup incide sobre o custo e imposto sobre a venda', () => {
    // 26,10 × 35% = 9,135 — comparado sem arredondar, que em binário cai
    // para 9,13 e faria o teste discordar da conta certa.
    const calculo = calcularItem(item(), PADROES);
    expect(calculo.lucroUnitario).toBeCloseTo(9.135, 10);
    expect(arredondar(calculo.impostoUnitario)).toBe(arredondar(calculo.precoFinalUnitario * 0.1));
  });

  it('bate com a planilha de origem quando não há frete (R$ 100 → R$ 158,89)', () => {
    const calculo = calcularItem(
      item({ ofertas: [oferta({ custoProduto: 100, frete: 0, outros: 0 })] }),
      PADROES,
    );
    expect(arredondar(calculo.precoFinalUnitario)).toBe(158.89);
  });

  it('markup do item vence o padrão da cotação', () => {
    expect(calcularItem(item({ markupAlvo: 50 }), PADROES).markupAlvo).toBe(50);
  });

  it('markup zero do item não é confundido com ausência', () => {
    const calculo = calcularItem(item({ markupAlvo: 0, markupMinimo: 0 }), PADROES);
    expect(calculo.markupAlvo).toBe(0);
    expect(calculo.lucroUnitario).toBe(0);
  });

  it('markup alvo nunca fica abaixo do mínimo', () => {
    const calculo = calcularItem(item({ markupMinimo: 40, markupAlvo: 10 }), PADROES);
    expect(calculo.markupAlvo).toBe(40);
    expect(calculo.precoFinalUnitario).toBe(calculo.precoReservaUnitario);
    expect(calculo.noLimite).toBe(true);
  });

  it('markup não tem teto — 250% é preço, não erro de digitação', () => {
    const calculo = calcularItem(item({ markupAlvo: 250 }), PADROES);
    expect(calculo.markupAlvo).toBe(250);
    // 26,10 × (1 + 8% + 250%) ÷ (1 − 10%) = 103,82
    expect(arredondar(calculo.precoFinalUnitario)).toBe(103.82);
  });

  it('markup negativo é zerado — vender abaixo do custo não é markup', () => {
    expect(calcularItem(item({ markupMinimo: -30 }), PADROES).markupMinimo).toBe(0);
  });

  it('tributo próprio do item vence o padrão', () => {
    expect(calcularItem(item({ impostos: 21.25 }), PADROES).tributos).toBeCloseTo(0.2125, 10);
  });

  it('carga tributária absurda é limitada em vez de estourar', () => {
    const calculo = calcularItem(item({ impostos: 100 }), PADROES);
    expect(calculo.tributos).toBe(0.9);
    expect(Number.isFinite(calculo.precoFinalUnitario)).toBe(true);
  });

  it('item sem fornecedor nenhum não derruba a conta', () => {
    const calculo = calcularItem(item({ ofertas: [], escolhida: '' }), PADROES);
    expect(calculo.custoUnitario).toBe(0);
    expect(calculo.precoFinalUnitario).toBe(0);
    expect(calculo.incompleto).toBe(true);
  });
});

describe('markup é entrada, margem é leitura', () => {
  it('a margem derivada do markup é sempre menor que ele', () => {
    const calculo = calcularItem(item(), PADROES);
    // Markup 35% do custo (R$ 26,10 → lucro R$ 9,135) sobre preço de
    // R$ 41,47 = 22,0% da venda.
    expect(calculo.markupAlvo).toBe(35);
    expect(calculo.margemAlvo).toBeCloseTo(22.028, 2);
    expect(calculo.margemAlvo).toBeLessThan(calculo.markupAlvo);
  });

  it('a margem do piso sai do preço de reserva, não do proposto', () => {
    const calculo = calcularItem(item(), PADROES);
    const lucroNoPiso = (calculo.custoUnitario * calculo.markupMinimo) / 100;
    expect(calculo.margemMinima).toBeCloseTo((lucroNoPiso / calculo.precoReservaUnitario) * 100, 6);
    expect(calculo.margemMinima).toBeLessThan(calculo.margemAlvo);
  });

  it('item sem preço não divide por zero para achar a margem', () => {
    const calculo = calcularItem(item({ ofertas: [], escolhida: '' }), PADROES);
    expect(calculo.margemAlvo).toBe(0);
    expect(calculo.margemMinima).toBe(0);
  });

  it('markup de 100% é margem de menos de 50% da venda', () => {
    const calculo = calcularItem(item({ markupAlvo: 100 }), PADROES);
    expect(calculo.margemAlvo).toBeLessThan(50);
  });
});

describe('régua do slider de markup', () => {
  it('nunca é menor que 100 — o começo da régua não muda com valor baixo', () => {
    expect(tetoDoSlider(0)).toBe(100);
    expect(tetoDoSlider(12)).toBe(100);
    expect(tetoDoSlider(45)).toBe(100);
  });

  it('sempre sobra curso à direita do valor atual', () => {
    for (const valor of [80, 100, 120, 200, 375]) {
      expect(tetoDoSlider(valor)).toBeGreaterThan(valor);
    }
  });

  it('cresce em degraus de 50', () => {
    expect(tetoDoSlider(80)).toBe(150);
    expect(tetoDoSlider(100)).toBe(150);
    expect(tetoDoSlider(120)).toBe(200);
    expect(tetoDoSlider(200)).toBe(300);
  });

  it('valor negativo não vira régua negativa', () => {
    expect(tetoDoSlider(-50)).toBe(100);
  });
});

describe('padrões da cotação', () => {
  it('a tela abre com markup de 12% a 45%', () => {
    expect(PADROES_INICIAIS.markupMinimo).toBe(12);
    expect(PADROES_INICIAIS.markupAlvo).toBe(45);
  });

  it('os alvos rápidos vão de 25% a 200%', () => {
    expect(ALVOS_RAPIDOS).toEqual([25, 50, 75, 100, 150, 200]);
  });
});

describe('comparação com o estimado do edital', () => {
  it('preço acima do estimado dá desvio positivo', () => {
    // Preço 41,47 contra estimado de 30,00 → 38,2% acima.
    expect(calcularItem(item(), PADROES).desvioReferencia).toBeCloseTo(38.233, 2);
  });

  it('preço abaixo do estimado dá desvio negativo', () => {
    // 16,20 × 1,43 ÷ 0,9 = 25,74 contra 30,00 → 14,2% abaixo.
    const alvo = item({ ofertas: [oferta({ custoProduto: 15, frete: 1.2 })] });
    expect(calcularItem(alvo, PADROES).desvioReferencia).toBeCloseTo(-14.2, 2);
  });

  it('edital sem referência não tem o que comparar', () => {
    expect(calcularItem(item({ valorReferencia: null }), PADROES).desvioReferencia).toBeNull();
  });

  it('referência zerada é edital sem valor publicado, não teto de R$ 0,00', () => {
    expect(calcularItem(item({ valorReferencia: 0 }), PADROES).desvioReferencia).toBeNull();
    expect(referenciaDe(item({ valorReferencia: 0 }))).toBeNull();
  });

  it('item ainda sem preço não vira "100% abaixo do estimado"', () => {
    const alvo = item({ ofertas: [oferta({ custoProduto: 0, frete: 0, outros: 0 })] });
    expect(calcularItem(alvo, PADROES).desvioReferencia).toBeNull();
  });
});

describe('escolha de fornecedor', () => {
  it('sem marcação válida, a primeira oferta entra na conta', () => {
    const alvo = item({
      ofertas: [oferta({ id: 'a' }), oferta({ id: 'b', custoProduto: 9 })],
      escolhida: 'inexistente',
    });
    expect(ofertaEscolhida(alvo)?.id).toBe('a');
  });

  it('melhor é o de menor custo com frete e extras', () => {
    // "b" tem produto mais barato, mas o frete o torna mais caro.
    const alvo = item({
      ofertas: [
        oferta({ id: 'a', nome: 'A', custoProduto: 10, frete: 0.5 }),
        oferta({ id: 'b', nome: 'B', custoProduto: 9.9, frete: 2 }),
      ],
      escolhida: 'a',
    });
    expect(melhorOferta(alvo)?.nome).toBe('A');
  });

  it('fornecedor sem preço não concorre a mais barato', () => {
    const alvo = item({
      ofertas: [
        oferta({ id: 'a', nome: 'A', custoProduto: 10, frete: 0 }),
        oferta({ id: 'b', nome: 'Em branco', custoProduto: 0, frete: 0 }),
      ],
      escolhida: 'a',
    });
    expect(melhorOferta(alvo)?.nome).toBe('A');
  });

  it('economia aparece quando o escolhido não é o mais barato', () => {
    const alvo = item({
      ofertas: [
        oferta({ id: 'a', custoProduto: 30, frete: 0 }),
        oferta({ id: 'b', custoProduto: 25, frete: 0 }),
      ],
      escolhida: 'a',
    });
    expect(calcularItem(alvo, PADROES).economiaUnitaria).toBe(5);
  });

  it('diferença de centésimo de centavo não vira sugestão de troca', () => {
    const alvo = item({
      ofertas: [
        oferta({ id: 'a', custoProduto: 10, frete: 0 }),
        oferta({ id: 'b', custoProduto: 9.999, frete: 0 }),
      ],
      escolhida: 'a',
    });
    expect(calcularItem(alvo, PADROES).economiaUnitaria).toBe(0);
  });

  it('custoUnitarioDa soma os três campos', () => {
    expect(custoUnitarioDa(oferta({ custoProduto: 10, frete: 2, outros: 0.5 }))).toBe(12.5);
  });
});

describe('totais da cotação', () => {
  const itens = [
    item(),
    item({
      id: 'i2',
      descricao: 'Toner HP 26A',
      quantidade: 12,
      impostos: 21.25,
      ofertas: [oferta({ id: 'o2', nome: 'InfoParts', custoProduto: 389, frete: 12 })],
      escolhida: 'o2',
    }),
  ];

  it('valor cotado é a soma dos preços finais', () => {
    const totais = totalizar(itens, PADROES);
    const esperado = itens.reduce((soma, i) => soma + calcularItem(i, PADROES).precoFinalTotal, 0);
    expect(totais.valorCotado).toBeCloseTo(esperado, 8);
  });

  it('capital inclui frete e custo dos produtos não', () => {
    const totais = totalizar(itens, PADROES);
    expect(totais.capital).toBeGreaterThan(totais.custoProdutos);
  });

  it('reserva fica abaixo do valor cotado e a folga é a diferença', () => {
    const totais = totalizar(itens, PADROES);
    expect(totais.precoReserva).toBeLessThan(totais.valorCotado);
    expect(totais.folga).toBeCloseTo(totais.valorCotado - totais.precoReserva, 8);
  });

  it('margem média é o lucro sobre a venda', () => {
    const totais = totalizar(itens, PADROES);
    expect(totais.margemMedia).toBeCloseTo((totais.lucroTotal / totais.valorCotado) * 100, 8);
    expect(totais.margemMedia).toBeCloseTo(totais.lucroPercentual, 8);
  });

  it('capital é o custo + transporte + garantia (GEN-29)', () => {
    const totais = totalizar(itens, PADROES);
    expect(totais.capital).toBeCloseTo(totais.custo + totais.transporte + totais.garantia, 8);
  });

  it('sem frete nem outros, o capital ainda passa do custo dos produtos (GEN-29)', () => {
    const so = [
      item({ ofertas: [oferta({ id: 'x', nome: 'X', custoProduto: 100, frete: 0, outros: 0 })] }),
    ];
    const totais = totalizar(so, PADROES);
    expect(totais.custo).toBe(totais.custoProdutos);
    expect(totais.capital).toBeGreaterThan(totais.custoProdutos);
  });

  it('markup médio é o lucro sobre o custo — bate com o markup dos itens (GEN-29)', () => {
    const totais = totalizar(itens, PADROES);
    expect(totais.markupMedio).toBeCloseTo((totais.lucroTotal / totais.custo) * 100, 8);
    // Markup é sempre maior que a margem: mesma conta, denominador menor.
    expect(totais.markupMedio).toBeGreaterThan(totais.margemMedia);
  });

  it('pendência conta item sem descrição ou sem preço', () => {
    const totais = totalizar(
      [
        item({ descricao: '   ' }),
        item({
          id: 'i3',
          ofertas: [oferta({ id: 'z', custoProduto: 0, frete: 0 })],
          escolhida: 'z',
        }),
      ],
      PADROES,
    );
    expect(totais.pendencias).toBe(2);
  });

  it('cotação vazia devolve zeros em vez de dividir por zero', () => {
    const totais = totalizar([], PADROES);
    expect(totais.valorCotado).toBe(0);
    expect(totais.margemMedia).toBe(0);
    expect(totais.markupMedio).toBe(0);
    expect(totais.lucroPercentual).toBe(0);
  });
});

describe('formatação', () => {
  it('moeda em pt-BR com duas casas', () => {
    expect(formatarMoeda(1234.5).replace(/ /g, ' ')).toBe('R$ 1.234,50');
  });

  it('percentual com uma casa', () => {
    expect(formatarPercentual(21.25)).toBe('21,3%');
    expect(formatarPercentual(8)).toBe('8%');
  });
});
