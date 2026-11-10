import datetime as dt
from decimal import Decimal
from unittest import mock

from django.test import TestCase
from rest_framework.test import APITestCase

from apps.accounts.models import User

from .models import ItemParticipado, OportunidadeSalva, PropostaDoItem
from .relatorio_mensal import relatorio_mensal

HOJE = dt.date(2026, 11, 9)


def salva(seq, prazo):
    return OportunidadeSalva.objects.create(
        cnpj_orgao="1", ano_compra="2026", sequencial_compra=str(seq), data_encerramento_proposta=prazo
    )


class RelatorioMensalTests(TestCase):
    def setUp(self):
        # Outubro: ganhou o item 22 (20 × R$ 11.999), com cotação (custo R$ 10.000).
        self.ganha = salva(1, dt.date(2026, 10, 1))
        ItemParticipado.objects.create(
            oportunidade=self.ganha, numero_item="22", quantidade=Decimal(20), valor_lance_final=Decimal(11999),
            vencedor_e_a_empresa=True, homologado_em=dt.date(2026, 10, 20),
        )  # fmt: skip
        # Outubro: perdeu o item 30 por R$ 1,00 (0,1%).
        self.perdida = salva(2, dt.date(2026, 10, 5))
        item = ItemParticipado.objects.create(
            oportunidade=self.perdida, numero_item="30", classificacao=2, quantidade=Decimal(1),
            valor_lance_final=Decimal(1299), vencedor_e_a_empresa=False, homologado_em=dt.date(2026, 10, 25),
        )  # fmt: skip
        PropostaDoItem.objects.create(item=item, classificacao=1, nome="HEALTH LIFE", marca="DELLAMED",
                                      valor_final=Decimal(1298), situacao="4")  # fmt: skip
        PropostaDoItem.objects.create(item=item, classificacao=2, nome="INSIDE", da_empresa=True,
                                      valor_final=Decimal(1299))  # fmt: skip
        # Salva sem participação: não conta.
        salva(3, dt.date(2026, 10, 7))

    def outubro(self, dados):
        return next(m for m in dados["meses"] if m["mes"] == "2026-10")

    def test_participou_ganhou_perdeu_e_faturamento(self):
        out = self.outubro(relatorio_mensal(12, HOJE))

        self.assertEqual((out["participou"], out["ganhou"], out["perdeu"]), (2, 1, 1))
        self.assertEqual(out["faturamento"], Decimal("239980.00"))
        self.assertIsNone(out["lucro"])  # sem cotação no Licita

    def test_lucro_so_com_cotacao(self):
        with mock.patch("apps.licitacoes.relatorio_mensal._custos", side_effect=lambda s: {"22": Decimal(10000)} if s.pk == self.ganha.pk else {}):
            out = self.outubro(relatorio_mensal(12, HOJE))

        self.assertEqual(out["lucro"], Decimal("39980.00"))

    def test_perdeu_por_pouco(self):
        pouco = relatorio_mensal(12, HOJE)["por_pouco"]

        self.assertEqual(len(pouco), 1)
        self.assertEqual((pouco[0]["item"], pouco[0]["diferenca"], pouco[0]["marca_vencedora"]), ("30", Decimal("1.00"), "DELLAMED"))

    def test_doze_meses_do_mais_recente_para_o_mais_antigo(self):
        meses = [m["mes"] for m in relatorio_mensal(12, HOJE)["meses"]]

        self.assertEqual((meses[0], meses[-1], len(meses)), ("2026-11", "2025-12", 12))


class RelatorioMensalApiTests(APITestCase):
    def test_pede_login(self):
        url = "/api/licitacoes/relatorios/mensal/"
        self.assertIn(self.client.get(url).status_code, (401, 403))
        self.client.force_authenticate(User.objects.create_user(email="a@b.com", password="x"))
        self.assertEqual(len(self.client.get(url + "?meses=6").json()["meses"]), 6)
