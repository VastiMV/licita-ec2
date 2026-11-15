"""A conta do Cotador — formação de preço com comparação de fornecedores.

Espelha `frontend/src/app/pages/oportunidades/cotador-modal/cotador.model.ts`,
que é quem recalcula a cada tecla enquanto o operador digita. Aqui a conta é
refeita no servidor por um motivo só: **o total gravado não pode vir do
cliente**. Se viesse, uma requisição adulterada (ou um frontend velho em
cache) gravaria um valor cotado que não corresponde aos itens salvos ao
lado dele — e a planilha exportada, que é a proposta que vai para o pregão,
sairia mentindo.

As duas implementações são ancoradas nos mesmos exemplos, em
`test_formulas.py` e em `cotador.model.spec.ts`: se uma derivar, o teste da
outra continua de pé e a divergência aparece.

## As duas bases de percentual

Trocá-las é o erro clássico desta conta:

- **% sobre o custo** — transporte, garantia e markup incidem sobre o que se
  paga ao fornecedor. "45% de markup" é acrescentar 45% do que custou. Markup
  não tem teto: em item barato passa de 100% sem esforço.
- **% sobre a venda** — os tributos (ICMS/Simples + PIS + COFINS + IPI +
  ISS, aqui já somados num número só) incidem sobre o preço final, que é
  justamente o que se quer descobrir.

Por isso o preço não é "custo + margem": é uma divisão por `(1 - tributos)`,
que embute o imposto que ainda vai cair sobre o próprio preço.

## Percentuais são percentuais

Aqui 8 significa 8% — o mesmo número que aparece no slider da tela, e não
a fração 0,08. A conversão para fração acontece só dentro das fórmulas, num lugar
só, o que elimina a classe inteira de bug "esqueci de dividir por 100".

Tudo em `Decimal`: é dinheiro, e `float` erra centavo em soma de muitos
itens.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

ZERO = Decimal("0")
UM = Decimal("1")
CEM = Decimal("100")
CENTAVO = Decimal("0.01")

# Teto da carga tributária usada na conta. Acima de 90% a divisão por
# `(1 - tributos)` explode o preço (e em 100% seria divisão por zero): não
# existe preço que feche a conta. Truncar é o mesmo que o protótipo faz,
# e mantém a tela mostrando um número em vez de infinito.
TETO_TRIBUTOS = Decimal("0.9")

# Diferença abaixo da qual dois custos são "o mesmo preço" — evita sugerir
# troca de fornecedor por meio centavo de arredondamento.
TOLERANCIA = Decimal("0.005")


@dataclass(frozen=True)
class Padroes:
    """Os percentuais que valem para a cotação inteira. Um item pode ter
    margem e tributo próprios; transporte e garantia são sempre daqui (não
    há regra por item para eles na tela)."""

    transporte: Decimal = ZERO
    garantia: Decimal = ZERO
    lucro_minimo: Decimal = ZERO
    lucro_maximo: Decimal = ZERO
    impostos: Decimal = ZERO


@dataclass(frozen=True)
class Oferta:
    """O preço de um fornecedor para um item."""

    identificador: object = None
    nome: str = ""
    custo_produto: Decimal = ZERO
    frete: Decimal = ZERO
    outros: Decimal = ZERO
    escolhida: bool = False

    @property
    def custo_unitario(self) -> Decimal:
        return self.custo_produto + self.frete + self.outros

    @property
    def tem_preco(self) -> bool:
        """Fornecedor sem preço não concorre a "mais barato" — senão o
        campo em branco venceria toda comparação."""

        return self.custo_produto > ZERO


@dataclass(frozen=True)
class Item:
    descricao: str = ""
    quantidade: Decimal = ZERO
    # `None` = "usa o padrão da cotação". Zero é um valor legítimo (margem
    # zero, item isento), por isso o ausente não pode ser representado por 0.
    margem_minima: Decimal | None = None
    margem_maxima: Decimal | None = None
    impostos: Decimal | None = None
    ofertas: list[Oferta] = field(default_factory=list)


@dataclass(frozen=True)
class ItemCalculado:
    escolhida: Oferta | None
    melhor: Oferta | None
    quantidade: Decimal
    custo_unitario: Decimal
    margem_minima: Decimal
    margem_maxima: Decimal
    tributos: Decimal
    """Fração já limitada pelo teto (0,10 = 10%)."""
    preco_final_unitario: Decimal
    preco_reserva_unitario: Decimal
    lucro_unitario: Decimal
    imposto_unitario: Decimal
    transporte_unitario: Decimal
    garantia_unitario: Decimal
    incompleto: bool
    """Item que ainda não dá para levar ao pregão: sem descrição ou sem
    preço do fornecedor escolhido."""
    economia_unitaria: Decimal
    """Quanto se economizaria por unidade trocando para o melhor
    fornecedor. Zero quando o escolhido já é o melhor."""

    @property
    def folga_unitaria(self) -> Decimal:
        """Espaço de negociação: do preço proposto até o piso."""

        return self.preco_final_unitario - self.preco_reserva_unitario

    @property
    def preco_final_total(self) -> Decimal:
        return self.preco_final_unitario * self.quantidade

    @property
    def preco_reserva_total(self) -> Decimal:
        return self.preco_reserva_unitario * self.quantidade

    @property
    def lucro_total(self) -> Decimal:
        return self.lucro_unitario * self.quantidade

    @property
    def custo_total(self) -> Decimal:
        return self.custo_unitario * self.quantidade


@dataclass(frozen=True)
class Totais:
    itens: int
    unidades: Decimal
    custo_produtos: Decimal
    """Só o que vai para o fornecedor, sem frete nem extras."""
    custo: Decimal
    """Produto + frete + outros do fornecedor (o custo sobre o qual incide o
    markup)."""
    capital: Decimal
    """O desembolso real para entregar: o custo + transporte + garantia
    (GEN-29, 14/11/2026 — decisão da operação: "tudo o que sai do bolso").
    Antes era só o custo, e ficava igual ao custo dos produtos quando não
    havia frete nem outros."""
    transporte: Decimal
    garantia: Decimal
    impostos: Decimal
    valor_cotado: Decimal
    preco_reserva: Decimal
    lucro_total: Decimal
    economia: Decimal
    """Quanto ainda dá para economizar trocando itens para o fornecedor mais
    barato."""
    pendencias: int

    @property
    def folga(self) -> Decimal:
        return self.valor_cotado - self.preco_reserva

    @property
    def lucro_percentual(self) -> Decimal:
        """Lucro como % da venda — a leitura de quem olha a proposta."""

        return _dividir(self.lucro_total, self.valor_cotado) * CEM

    @property
    def margem_media(self) -> Decimal:
        """A margem real da cotação: lucro como % da **venda**.

        Coincide com `lucro_percentual` por definição — a tela mostra o
        mesmo número no painel de composição e no resultado."""

        return _dividir(self.lucro_total, self.valor_cotado) * CEM

    @property
    def markup_medio(self) -> Decimal:
        """Lucro como % do **custo** (produto + frete + outros) — bate com o
        markup configurado nos itens. Continua sobre o custo, não sobre o
        capital com transporte e garantia (decisão da operação, 14/11/2026,
        GEN-29)."""

        return _dividir(self.lucro_total, self.custo) * CEM


def _dividir(numerador: Decimal, denominador: Decimal) -> Decimal:
    """Divisão que devolve zero em vez de estourar. É o `IFERROR(...;0)` que
    a planilha de origem repete em toda coluna calculada — um item sem
    quantidade ou uma cotação vazia não podem derrubar a tela."""

    return ZERO if denominador == ZERO else numerador / denominador


def _ou_padrao(valor: Decimal | None, padrao: Decimal) -> Decimal:
    return padrao if valor is None else valor


def escolhida(item: Item) -> Oferta | None:
    """A oferta que entra na conta. Sem marcação explícita, a primeira —
    um item recém-criado tem um fornecedor só e ainda não foi marcado."""

    for oferta in item.ofertas:
        if oferta.escolhida:
            return oferta
    return item.ofertas[0] if item.ofertas else None


def melhor(item: Item) -> Oferta | None:
    """A oferta de menor custo unitário entre as que têm preço."""

    com_preco = [oferta for oferta in item.ofertas if oferta.tem_preco]
    if not com_preco:
        return None
    return min(com_preco, key=lambda oferta: oferta.custo_unitario)


def calcular_item(item: Item, padroes: Padroes) -> ItemCalculado:
    oferta = escolhida(item)
    melhor_oferta = melhor(item)

    custo_unitario = oferta.custo_unitario if oferta else ZERO
    quantidade = max(item.quantidade, ZERO)

    # Transporte e garantia entram como acréscimo sobre o custo, junto com
    # a margem — é o "1 + over + m" do protótipo.
    sobre_custo = (padroes.transporte + padroes.garantia) / CEM

    margem_minima = _ou_padrao(item.margem_minima, padroes.lucro_minimo)
    # A máxima nunca fica abaixo da mínima: os dois sliders se travam entre
    # si na tela, e uma cotação antiga (salva antes de o mínimo subir) não
    # pode passar a propor menos do que o próprio piso.
    margem_maxima = max(_ou_padrao(item.margem_maxima, padroes.lucro_maximo), margem_minima)

    tributos = min(_ou_padrao(item.impostos, padroes.impostos) / CEM, TETO_TRIBUTOS)

    def preco(margem: Decimal) -> Decimal:
        return _dividir(custo_unitario * (UM + sobre_custo + margem / CEM), UM - tributos)

    preco_final = preco(margem_maxima)
    economia_unitaria = ZERO
    if (
        melhor_oferta
        and oferta
        and melhor_oferta is not oferta
        and melhor_oferta.custo_unitario < custo_unitario - TOLERANCIA
    ):
        economia_unitaria = custo_unitario - melhor_oferta.custo_unitario

    return ItemCalculado(
        escolhida=oferta,
        melhor=melhor_oferta,
        quantidade=quantidade,
        custo_unitario=custo_unitario,
        margem_minima=margem_minima,
        margem_maxima=margem_maxima,
        tributos=tributos,
        preco_final_unitario=preco_final,
        preco_reserva_unitario=preco(margem_minima),
        lucro_unitario=custo_unitario * margem_maxima / CEM,
        imposto_unitario=preco_final * tributos,
        transporte_unitario=custo_unitario * padroes.transporte / CEM,
        garantia_unitario=custo_unitario * padroes.garantia / CEM,
        incompleto=not (item.descricao or "").strip() or not oferta or not oferta.tem_preco,
        economia_unitaria=economia_unitaria,
    )


def totalizar(itens: list[Item], padroes: Padroes) -> Totais:
    """Soma da cotação inteira. Arredonda ao centavo só no fim — arredondar
    item a item acumularia erro na soma."""

    calculados = [calcular_item(item, padroes) for item in itens]

    def somar(extrair) -> Decimal:
        return sum((extrair(c) for c in calculados), ZERO).quantize(CENTAVO)

    return Totais(
        itens=len(itens),
        unidades=sum((c.quantidade for c in calculados), ZERO),
        custo_produtos=somar(
            lambda c: (c.escolhida.custo_produto if c.escolhida else ZERO) * c.quantidade
        ),
        custo=somar(lambda c: c.custo_total),
        capital=somar(lambda c: c.custo_total)
        + somar(lambda c: c.transporte_unitario * c.quantidade)
        + somar(lambda c: c.garantia_unitario * c.quantidade),
        transporte=somar(lambda c: c.transporte_unitario * c.quantidade),
        garantia=somar(lambda c: c.garantia_unitario * c.quantidade),
        impostos=somar(lambda c: c.imposto_unitario * c.quantidade),
        valor_cotado=somar(lambda c: c.preco_final_total),
        preco_reserva=somar(lambda c: c.preco_reserva_total),
        lucro_total=somar(lambda c: c.lucro_total),
        economia=somar(lambda c: c.economia_unitaria * c.quantidade),
        pendencias=sum(1 for c in calculados if c.incompleto),
    )


def decimal(valor: object, padrao: Decimal | None = ZERO) -> Decimal | None:
    """JSON traz número como int/float/str conforme o cliente. Converte pela
    `str` de propósito: `Decimal(0.1)` guarda o erro binário do float e
    `Decimal("0.1")` não."""

    if isinstance(valor, Decimal):
        return valor
    if valor is None or valor == "":
        return padrao
    try:
        return Decimal(str(valor))
    except ArithmeticError:
        return padrao
