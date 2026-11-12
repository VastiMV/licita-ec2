"""Proposta retirada e a ronda depois da sessão (GEN-71, 12/11/2026).

Caso real: Dispensa 27/2026 (Cabedelo). Ele lançou preço, a sessão passou,
ele retirou a proposta e não participou. A compra ficava em "Aguardando
sessão" para sempre: a leitura "não é mais participante" era ignorada, os
itens com preço continuavam lá e a ronda só relia compras na fase 3 ou 4.
Decisão da operação: vai para **Descartadas · Proposta retirada**.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from django.utils import timezone

from apps.licitacoes.encerradas import classificar
from apps.licitacoes.models import ItemParticipado, ParticipacaoCompra

from .ingestao import receber
from .ronda import consultas
from .test_propostas import CNPJ, CUBATAO, HOJE, cartao
from .test_vigia import BASE, _Base, salva


def proposta_do_item(numero: str) -> str:
    return f"{BASE}/{CUBATAO}/em-selecao-fornecedores/participacoes/{CNPJ}/itens/{numero}/propostas?filtro=2"


def na_ronda(numero: str) -> str:
    """O mesmo endereço como a ronda pede (sem o domínio)."""
    return proposta_do_item(numero).removeprefix("https://cnetmobile.estaleiro.serpro.gov.br")


class _ComPreco(_Base):
    """Compra antes da sessão, com preço lançado em dois itens."""

    def setUp(self):
        super().setUp()
        self.s = salva(prazo_dias=-1)
        self.participacao = ParticipacaoCompra.objects.create(
            oportunidade=self.s,
            fase_compra="1",
            proposta_cadastrada=True,
            sessao_abre_em=timezone.now() - dt.timedelta(hours=10),
        )
        for numero in ("1", "2"):
            ItemParticipado.objects.create(
                oportunidade=self.s, numero_item=numero, valor_proposta_inicial=Decimal("100")
            )

    def itens(self):
        return {i.numero_item: i for i in ItemParticipado.objects.filter(oportunidade=self.s)}


class PropostaRetiradaTests(_ComPreco):
    def test_antes_da_correcao_ficava_aguardando_sessao(self):
        self.assertEqual(cartao(self.s)["etapa"], "aguardando_sessao")

    def test_nao_e_mais_participante_vai_para_descartadas_proposta_retirada(self):
        resumo = receber(
            f"{BASE}/{CUBATAO}/participacao",
            {"isFornecedorParticipante": False, "faseCompraFaseExterna": "3"},
        )

        self.assertEqual(resumo["retirados"], 2)
        self.assertIsNone(cartao(self.s))
        self.assertEqual(classificar(HOJE)[self.s.pk], ("descartadas", "proposta_retirada", HOJE))
        self.participacao.refresh_from_db()
        self.assertEqual(self.participacao.fase_compra, "3")  # a fase também é gravada agora
        self.assertIs(self.participacao.proposta_cadastrada, False)

    def test_nao_participante_sem_preco_no_licita_nao_vira_retirada(self):
        ItemParticipado.objects.filter(oportunidade=self.s).update(valor_proposta_inicial=None)

        resumo = receber(f"{BASE}/{CUBATAO}/participacao", {"isFornecedorParticipante": False})

        self.assertEqual(resumo["retirados"], 0)
        self.assertFalse(any(i.retirada_em for i in self.itens().values()))

    def test_compra_desconhecida_nao_participante_continua_ignorada(self):
        outra = "98957106000012026"
        resumo = receber(f"{BASE}/{outra}/participacao", {"isFornecedorParticipante": False})

        self.assertEqual(resumo, {"tipo": "participacao", "compras": 0, "criadas": 0})

    def test_meus_itens_vazio_retira_todos(self):
        resumo = receber(f"{BASE}/{CUBATAO}/itens/em-selecao-fornecedores?filtro=2&pagina=0", [])

        self.assertEqual(resumo["retirados"], 2)
        self.assertEqual(classificar(HOJE)[self.s.pk][:2], ("descartadas", "proposta_retirada"))

    def test_item_volta_sem_a_proposta_retira_so_aquele_item(self):
        resumo = receber(proposta_do_item("1"), [{"identificador": "1", "numero": 1, "fase": "E"}])

        self.assertEqual(resumo["retirados"], 1)
        itens = self.itens()
        self.assertIsNotNone(itens["1"].retirada_em)
        self.assertIsNone(itens["2"].retirada_em)
        c = cartao(self.s)  # o item 2 continua: a licitação fica na Torre
        self.assertIsNotNone(c)
        self.assertEqual(
            {i["numero"]: i["perdido"] for i in c["itens"]}, {"1": "proposta retirada", "2": ""}
        )

    def test_retirou_um_e_perdeu_o_outro_e_perdida_em_encerradas(self):
        ItemParticipado.objects.filter(oportunidade=self.s, numero_item="2").update(vencedor_e_a_empresa=False)

        receber(proposta_do_item("1"), [{"identificador": "1", "numero": 1}])

        self.assertEqual(classificar(HOJE)[self.s.pk][:2], ("encerradas", "perdida"))

    def test_preco_lido_de_novo_desfaz_a_retirada(self):
        receber(f"{BASE}/{CUBATAO}/participacao", {"isFornecedorParticipante": False})

        receber(
            proposta_do_item("1"),
            [{"identificador": "1", "numero": 1, "fase": "E", "propostaItem": {
                "participante": {"identificacao": CNPJ},
                "valores": {"valorPropostaInicial": {"valorInformado": 90}}}}],
        )  # fmt: skip

        self.assertIsNone(self.itens()["1"].retirada_em)
        self.assertIsNotNone(cartao(self.s))


class RondaDepoisDaSessaoTests(_ComPreco):
    def da_empresa(self):
        return [c for c in consultas() if "/participacoes/" in c and "filtro=2" in c]

    def test_sessao_passou_e_a_compra_continua_antes_da_sessao_entra_na_ronda(self):
        self.assertEqual(self.da_empresa(), [na_ronda("1"), na_ronda("2")])

    def test_sessao_ainda_nao_abriu_nao_entra(self):
        ParticipacaoCompra.objects.filter(pk=self.participacao.pk).update(
            sessao_abre_em=timezone.now() + dt.timedelta(hours=5)
        )

        self.assertEqual(self.da_empresa(), [])

    def test_sem_data_de_sessao_entra_quando_o_prazo_passou(self):
        ParticipacaoCompra.objects.filter(pk=self.participacao.pk).update(sessao_abre_em=None)

        self.assertEqual(len(self.da_empresa()), 2)

        self.s.data_encerramento_proposta = HOJE + dt.timedelta(days=3)
        self.s.save(update_fields=["data_encerramento_proposta"])
        self.assertEqual(self.da_empresa(), [])

    def test_item_retirado_sai_da_ronda(self):
        ItemParticipado.objects.filter(oportunidade=self.s, numero_item="1").update(retirada_em=timezone.now())

        self.assertEqual(self.da_empresa(), [na_ronda("2")])
