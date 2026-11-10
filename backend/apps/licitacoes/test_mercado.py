import datetime as dt
from decimal import Decimal

from django.test import TestCase

from apps.catalogo.models import Pdm

from .mercado import achar_catmat, atualizar, relatorio_de_mercado, renovar_todos
from .models import ItemParticipado, MercadoDoItem, OportunidadeSalva

HOJE = dt.date(2026, 11, 9)
# A cadeira de Cubatão (55/2026, item 2), como vem no edital.
CADEIRA = (
    "Cadeira De Rodas Manual Para Locomoção modelo construtivo: dobrável, material da estrutura: liga de "
    "alumínio c/ revestimento, capacidade: de 171 a 200, tamanho: adulto"
)


class FakeCompras:
    def itens_do_pdm(self, codigo_pdm):
        return [
            {"codigoItem": 637928, "descricaoItem": CADEIRA.upper().replace("200,", "200 ,")},
            {"codigoItem": 637933, "descricaoItem": CADEIRA.upper().replace("171 A 200", "100 A 130")},
        ]

    def precos_praticados(self, tipo, codigo, inicio, fim):
        if tipo == "codigoItemCatalogo":
            return [
                {"precoUnitario": 1200, "dataCompra": "2026-09-15", "marca": "Dellamed"},
                {"precoUnitario": 1300, "dataCompra": "2026-07-09", "marca": "Dellamed"},
                {"precoUnitario": 1400, "dataCompra": "2025-06-01", "marca": "Hidrolight"},
            ]
        return [{"precoUnitario": p, "dataCompra": "2026-10-01", "marca": "Prolife"} for p in (500, 900, 1500, 2000)]


class MercadoTests(TestCase):
    def setUp(self):
        Pdm.objects.create(codigo_pdm=30428, nome_pdm="CADEIRA DE RODAS MANUAL PARA LOCOMOÇÃO",
                           nome_normalizado="CADEIRA DE RODAS MANUAL PARA LOCOMOCAO")  # fmt: skip
        Pdm.objects.create(codigo_pdm=4076, nome_pdm="Cadeira De Rodas", nome_normalizado="CADEIRA DE RODAS")
        salva = OportunidadeSalva.objects.create(cnpj_orgao="1", ano_compra="2026", sequencial_compra="55")
        ItemParticipado.objects.create(oportunidade=salva, numero_item="2", descricao=CADEIRA,
                                       valor_lance_final=Decimal(1200))  # fmt: skip

    def test_acha_o_item_exato_e_nao_o_de_outra_capacidade(self):
        codigo, nota = achar_catmat(CADEIRA, FakeCompras().itens_do_pdm(30428))

        self.assertEqual(codigo, 637928)
        self.assertGreaterEqual(nota, 0.98)

    def test_media_marcas_por_periodo_e_a_oferta_dele(self):
        registro = atualizar(CADEIRA, FakeCompras(), HOJE)

        self.assertEqual((registro.codigo_pdm, registro.codigo_catmat), (30428, 637928))
        exato = registro.dados["exato"]
        self.assertEqual((exato["3"]["compras"], exato["6"]["compras"], exato["24"]["compras"]), (1, 2, 3))
        self.assertEqual(exato["6"]["media"], 1250.0)
        self.assertEqual(exato["24"]["marcas"][0], {"marca": "DELLAMED", "vezes": 2})
        self.assertTrue(exato["6"]["poucos_dados"])
        self.assertEqual(registro.dados["grupo"]["12"]["compras"], 4)

        bloco = relatorio_de_mercado()[0]
        self.assertEqual((bloco["media_dele"], bloco["codigo_catmat"]), (1200.0, 637928))

    def test_renova_so_o_que_esta_velho(self):
        self.assertEqual(renovar_todos(FakeCompras(), HOJE), 1)
        self.assertEqual(renovar_todos(FakeCompras(), HOJE), 0)
        self.assertEqual(MercadoDoItem.objects.count(), 1)
