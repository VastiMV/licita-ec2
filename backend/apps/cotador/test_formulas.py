"""Testes da conta do Cotador.

Sem Django de propósito: `formulas.py` não conhece model nem banco, então o
teste da regra de negócio roda sozinho (`python -m unittest`), o que é o que
mantém a conta verificável mesmo sem Postgres no ambiente.

Os números vêm de duas âncoras:

- o exemplo do protótipo (`docs/Mockups/cotador`): resma de papel a R$ 24,90
  + R$ 1,20 de frete, transporte 8%, tributos 10%, markup 35%;
- o exemplo da planilha de origem, que o cotador antigo também usa
  (R$ 100 + 8% de transporte + 10% de imposto + 35% de lucro = R$ 158,89) —
  as duas fórmulas coincidem quando não há frete nem outros custos, e é bom
  que isso continue verdade.

O mesmo conjunto está em `cotador.model.spec.ts`, do lado do frontend: se
uma das duas implementações derivar, o teste da outra continua de pé e a
divergência aparece.
"""

from __future__ import annotations

import unittest
from decimal import Decimal

from .formulas import Item, Oferta, Padroes, calcular_item, escolhida, melhor, totalizar

D = Decimal


# Escritos aqui, e não lidos dos defaults do model: o padrão com que a tela
# abre pode mudar (mudou para markup 12%–45%) sem que a conta mude, e são
# estes números que estão ancorados do outro lado, em `cotador.model.spec.ts`.
PADROES = Padroes(
    transporte=D("8"),
    garantia=D("0"),
    lucro_minimo=D("10"),
    lucro_maximo=D("35"),
    impostos=D("10"),
)


def oferta(nome="Fornecedor", custo="0", frete="0", outros="0", escolhida=False) -> Oferta:
    return Oferta(
        identificador=nome,
        nome=nome,
        custo_produto=D(custo),
        frete=D(frete),
        outros=D(outros),
        escolhida=escolhida,
    )


def item(**kwargs) -> Item:
    base = {
        "descricao": "Papel A4 75g — resma 500fl",
        "quantidade": D("120"),
        "ofertas": [oferta("Distribuidora Sul", "24.90", "1.20", escolhida=True)],
    }
    return Item(**{**base, **kwargs})


class PrecoDeUmItemTests(unittest.TestCase):
    def test_custo_unitario_soma_produto_frete_e_outros(self):
        calculo = calcular_item(item(), PADROES)
        self.assertEqual(calculo.custo_unitario, D("26.10"))

    def test_preco_final_embute_transporte_margem_e_tributo(self):
        # 26,10 × (1 + 8% + 35%) ÷ (1 − 10%) = 41,47
        calculo = calcular_item(item(), PADROES)
        self.assertEqual(calculo.preco_final_unitario.quantize(D("0.01")), D("41.47"))

    def test_preco_de_reserva_usa_a_margem_minima(self):
        # 26,10 × (1 + 8% + 10%) ÷ (1 − 10%) = 34,22 — o piso da negociação.
        calculo = calcular_item(item(), PADROES)
        self.assertEqual(calculo.preco_reserva_unitario.quantize(D("0.01")), D("34.22"))
        self.assertGreater(calculo.folga_unitaria, 0)

    def test_lucro_incide_sobre_o_custo_e_imposto_sobre_a_venda(self):
        calculo = calcular_item(item(), PADROES)
        self.assertEqual(calculo.lucro_unitario, D("9.135"))
        self.assertEqual(
            calculo.imposto_unitario.quantize(D("0.01")),
            (calculo.preco_final_unitario * D("0.10")).quantize(D("0.01")),
        )

    def test_bate_com_a_planilha_de_origem_quando_nao_ha_frete(self):
        """R$ 100 + 8% transporte + 10% imposto + 35% lucro = R$ 158,89 —
        o mesmo exemplo de `apps/licitacoes/cotacao.py`."""

        calculo = calcular_item(
            item(ofertas=[oferta(custo="100", escolhida=True)]), PADROES
        )
        self.assertEqual(calculo.preco_final_unitario.quantize(D("0.01")), D("158.89"))

    def test_markup_do_item_vence_o_padrao_da_cotacao(self):
        calculo = calcular_item(item(margem_maxima=D("50")), PADROES)
        self.assertEqual(calculo.margem_maxima, D("50"))

    def test_markup_zero_do_item_nao_e_confundido_com_ausencia(self):
        """Zero é decisão (vender no custo), não "usa o padrão" — por isso o
        ausente é `None`."""

        calculo = calcular_item(item(margem_maxima=D("0"), margem_minima=D("0")), PADROES)
        self.assertEqual(calculo.margem_maxima, D("0"))
        self.assertEqual(calculo.lucro_unitario, D("0"))

    def test_markup_alvo_nunca_fica_abaixo_do_minimo(self):
        calculo = calcular_item(item(margem_minima=D("40"), margem_maxima=D("10")), PADROES)
        self.assertEqual(calculo.margem_maxima, D("40"))
        self.assertEqual(calculo.preco_final_unitario, calculo.preco_reserva_unitario)

    def test_markup_nao_tem_teto(self):
        """250% de markup é preço de item barato, não erro de digitação: a
        conta precisa aceitar (o teto de 100% do serializer saiu junto)."""

        calculo = calcular_item(item(margem_maxima=D("250")), PADROES)
        self.assertEqual(calculo.margem_maxima, D("250"))
        # 26,10 × (1 + 8% + 250%) ÷ (1 − 10%) = 103,82
        self.assertEqual(calculo.preco_final_unitario.quantize(D("0.01")), D("103.82"))

    def test_tributo_proprio_do_item_vence_o_padrao(self):
        calculo = calcular_item(item(impostos=D("21.25")), PADROES)
        self.assertEqual(calculo.tributos, D("0.2125"))

    def test_carga_tributaria_absurda_e_limitada_em_vez_de_estourar(self):
        calculo = calcular_item(item(impostos=D("100")), PADROES)
        self.assertEqual(calculo.tributos, D("0.9"))
        self.assertGreater(calculo.preco_final_unitario, 0)

    def test_item_sem_fornecedor_nao_derruba_a_conta(self):
        calculo = calcular_item(item(ofertas=[]), PADROES)
        self.assertEqual(calculo.custo_unitario, D("0"))
        self.assertEqual(calculo.preco_final_unitario, D("0"))
        self.assertTrue(calculo.incompleto)


class EscolhaDeFornecedorTests(unittest.TestCase):
    def test_sem_marcacao_a_primeira_oferta_entra_na_conta(self):
        primeira = oferta("A", "10")
        alvo = item(ofertas=[primeira, oferta("B", "9")])
        self.assertIs(escolhida(alvo), primeira)

    def test_melhor_e_o_de_menor_custo_com_frete_e_extras(self):
        # "B" tem produto mais barato, mas o frete o torna mais caro.
        alvo = item(
            ofertas=[oferta("A", "10", "0.50", escolhida=True), oferta("B", "9.90", "2")]
        )
        self.assertEqual(melhor(alvo).nome, "A")

    def test_fornecedor_sem_preco_nao_concorre_a_mais_barato(self):
        alvo = item(ofertas=[oferta("A", "10", escolhida=True), oferta("Em branco", "0")])
        self.assertEqual(melhor(alvo).nome, "A")

    def test_economia_aparece_quando_o_escolhido_nao_e_o_mais_barato(self):
        alvo = item(ofertas=[oferta("Caro", "30", escolhida=True), oferta("Barato", "25")])
        calculo = calcular_item(alvo, PADROES)
        self.assertEqual(calculo.economia_unitaria, D("5"))

    def test_diferenca_de_centesimo_de_centavo_nao_vira_sugestao_de_troca(self):
        alvo = item(
            ofertas=[oferta("A", "10.000", escolhida=True), oferta("B", "9.999")]
        )
        self.assertEqual(calcular_item(alvo, PADROES).economia_unitaria, D("0"))


class TotaisTests(unittest.TestCase):
    def setUp(self):
        self.itens = [
            item(),
            item(
                descricao="Toner HP 26A",
                quantidade=D("12"),
                impostos=D("21.25"),
                ofertas=[oferta("InfoParts", "389", "12", escolhida=True)],
            ),
        ]

    def test_valor_cotado_e_a_soma_dos_precos_finais(self):
        totais = totalizar(self.itens, PADROES)
        esperado = sum(
            (calcular_item(i, PADROES).preco_final_total for i in self.itens), D("0")
        )
        self.assertEqual(totais.valor_cotado, esperado.quantize(D("0.01")))

    def test_capital_inclui_frete_e_custo_dos_produtos_nao(self):
        totais = totalizar(self.itens, PADROES)
        self.assertGreater(totais.capital, totais.custo_produtos)

    def test_reserva_fica_abaixo_do_valor_cotado_e_a_folga_e_a_diferenca(self):
        totais = totalizar(self.itens, PADROES)
        self.assertLess(totais.preco_reserva, totais.valor_cotado)
        self.assertEqual(totais.folga, totais.valor_cotado - totais.preco_reserva)

    def test_margem_media_e_lucro_sobre_a_venda(self):
        totais = totalizar(self.itens, PADROES)
        esperado = totais.lucro_total / totais.valor_cotado * 100
        self.assertEqual(totais.margem_media, esperado)
        self.assertEqual(totais.margem_media, totais.lucro_percentual)

    def test_capital_e_o_custo_mais_transporte_e_garantia(self):
        # GEN-29 (14/11/2026): "tudo o que sai do bolso".
        totais = totalizar(self.itens, PADROES)
        self.assertEqual(totais.capital, totais.custo + totais.transporte + totais.garantia)

    def test_sem_frete_nem_outros_o_capital_ainda_e_maior_que_o_custo_dos_produtos(self):
        # O caso do GEN-29: sem frete e outros no fornecedor, os dois números
        # ficavam iguais. Com transporte nas configurações, não ficam mais.
        totais = totalizar([item(ofertas=[oferta("X", "100", escolhida=True)])], PADROES)
        self.assertEqual(totais.custo, totais.custo_produtos)
        self.assertGreater(totais.capital, totais.custo_produtos)

    def test_markup_medio_e_lucro_sobre_o_custo(self):
        # Continua sobre o custo (produto + frete + outros), não sobre o
        # capital com transporte e garantia — decisão de 14/11/2026, GEN-29.
        totais = totalizar(self.itens, PADROES)
        esperado = totais.lucro_total / totais.custo * 100
        self.assertEqual(totais.markup_medio, esperado)
        # Mesma conta, denominador menor: markup é sempre maior que a margem.
        self.assertGreater(totais.markup_medio, totais.margem_media)

    def test_pendencia_conta_item_sem_descricao_ou_sem_preco(self):
        totais = totalizar(
            [item(descricao="  "), item(ofertas=[oferta("X", "0", escolhida=True)])],
            PADROES,
        )
        self.assertEqual(totais.pendencias, 2)

    def test_cotacao_vazia_devolve_zeros_em_vez_de_dividir_por_zero(self):
        totais = totalizar([], PADROES)
        self.assertEqual(totais.valor_cotado, D("0"))
        self.assertEqual(totais.margem_media, D("0"))
        self.assertEqual(totais.markup_medio, D("0"))
        self.assertEqual(totais.lucro_percentual, D("0"))


if __name__ == "__main__":
    unittest.main()
