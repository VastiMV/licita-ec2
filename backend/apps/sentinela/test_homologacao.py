"""Homologação pela proposta da empresa e o teto da ronda (GEN-89, 14/11/2026).

Caso real: Pregão 56/2026, item 22 — homologado no Compras.gov, mas no
Licita em Disputar › Finalizadas: a homologação só vinha das "propostas de
todos" (o fim da fila da ronda, cortado pelo teto de 60) ou do PNCP.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from apps.licitacoes.models import ItemParticipado, ParticipacaoCompra

from .ingestao import receber
from .ronda import MAXIMO, caminho_das_propostas, consultas
from .test_propostas import CNPJ, CUBATAO, HOJE, cartao
from .test_vigia import BASE, _Base, salva


def proposta_do_item(numero: str, situacao: str, homologado: bool):
    url = f"{BASE}/{CUBATAO}/em-selecao-fornecedores/participacoes/{CNPJ}/itens/{numero}/propostas?filtro=2"
    item = {
        "identificador": numero,
        "numero": int(numero),
        "fase": "AE",
        "homologado": homologado,
        "propostaItem": {
            "participante": {"identificacao": CNPJ},
            "classificacao": 1,
            "situacao": situacao,
            "valores": {"valorPropostaInicial": {"valorInformado": 100}},
        },
    }
    return url, [item]


class HomologadoPelaPropostaDaEmpresaTests(_Base):
    def setUp(self):
        super().setUp()
        self.s = salva()
        ParticipacaoCompra.objects.create(oportunidade=self.s, fase_compra="4", proposta_cadastrada=True)
        self.item = ItemParticipado.objects.create(
            oportunidade=self.s, numero_item="22", classificacao=1, situacao_proposta="6", fase_item="AE",
            valor_proposta_inicial=Decimal("100"),
        )  # fmt: skip

    def test_adjudicada_fica_em_finalizadas_ate_saber_da_homologacao(self):
        self.assertEqual(cartao(self.s)["etapa"], "finalizadas")

    def test_homologado_e_adjudicada_para_ela_vai_para_homologado(self):
        receber(*proposta_do_item("22", situacao="6", homologado=True))

        self.item.refresh_from_db()
        self.assertIs(self.item.vencedor_e_a_empresa, True)
        self.assertEqual(self.item.homologado_em, HOJE)
        self.assertEqual(cartao(self.s)["etapa"], "homologado")

    def test_homologado_mas_a_proposta_dela_nao_e_a_adjudicada_nao_muda(self):
        receber(*proposta_do_item("22", situacao="4", homologado=True))

        self.item.refresh_from_db()
        self.assertIsNone(self.item.vencedor_e_a_empresa)
        self.assertIsNone(self.item.homologado_em)

    def test_nao_homologado_nao_muda(self):
        receber(*proposta_do_item("22", situacao="6", homologado=False))

        self.item.refresh_from_db()
        self.assertIsNone(self.item.vencedor_e_a_empresa)

    def test_data_da_homologacao_ja_conhecida_e_mantida(self):
        antiga = HOJE - dt.timedelta(days=3)
        ItemParticipado.objects.filter(pk=self.item.pk).update(homologado_em=antiga)

        receber(*proposta_do_item("22", situacao="6", homologado=True))

        self.item.refresh_from_db()
        self.assertEqual(self.item.homologado_em, antiga)


class TetoDaRondaTests(_Base):
    def test_teto_e_100(self):
        self.assertEqual(MAXIMO, 100)

    def test_com_a_fila_cheia_as_propostas_de_todos_ainda_entram(self):
        # 25 itens na frente numa compra depois da sessão: 3 consultas cada
        # (proposta, recurso, diligências) = 75. Com o teto de 60, as
        # "propostas de todos" (fim da fila) eram cortadas.
        s = salva()
        ParticipacaoCompra.objects.create(oportunidade=s, fase_compra="4", proposta_cadastrada=True)
        for n in range(1, 26):
            ItemParticipado.objects.create(oportunidade=s, numero_item=str(n), classificacao=1)

        lista = consultas()

        self.assertLessEqual(len(lista), MAXIMO)
        self.assertIn(caminho_das_propostas(CUBATAO, "1"), lista)
