"""Testes da Torre de Controle (`/api/licitacoes/torre/`).

Os casos são os pregões reais da operação em 07/11/2026 — o que o
Compras.gov.br, o PNCP e o Portal da Transparência mostraram — para a regra
de etapa nascer do que de fato acontece, não do que se imagina:

- 61/2026 IF Farroupilha, item 22: 1º lugar, anexo enviado, aguardando julgamento;
- 56/2026 PM-DF, item 22: 1º lugar, fornecedor habilitado (ganho); itens 6 e 9 perdendo;
- 112/2026 IBAMA e 201/2026 UFVJM: homologados no PNCP, ainda sem contrato ou empenho.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.cotador.test_views import cotacao_payload

from .models import (
    DocumentoFinanceiro,
    Entrega,
    Fonte,
    ItemParticipado,
    OportunidadeSalva,
    ParticipacaoCompra,
)


class TorreTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="operador@empresa.com", password="x")
        self.client.force_authenticate(self.user)
        self.hoje = timezone.localdate()
        self._seq = 0

    # -- montagem -----------------------------------------------------------

    def salva(self, prazo_em_dias: int | None = 10, **extras) -> OportunidadeSalva:
        self._seq += 1
        prazo = self.hoje + dt.timedelta(days=prazo_em_dias) if prazo_em_dias is not None else None
        extras.setdefault("uasg", "158127")
        return OportunidadeSalva.objects.create(
            cnpj_orgao="10662072000158",
            ano_compra="2026",
            sequencial_compra=str(self._seq),
            objeto=f"Edital {self._seq}",
            data_encerramento_proposta=prazo,
            **extras,
        )

    def cotar(self, salva):
        resposta = self.client.post(
            "/api/cotador/cotacoes/", cotacao_payload(oportunidade_id=salva.pk), format="json"
        )
        self.assertIn(resposta.status_code, (200, 201))

    def item(self, salva, numero="22", **campos) -> ItemParticipado:
        return ItemParticipado.objects.create(oportunidade=salva, numero_item=numero, **campos)

    def torre(self):
        resposta = self.client.get("/api/licitacoes/torre/")
        self.assertEqual(resposta.status_code, 200)
        return resposta.data

    def cartao(self, torre, salva):
        for estagio in torre["estagios"]:
            for cartao in estagio["cartoes"]:
                if cartao["id"] == salva.pk:
                    return cartao
        return None

    def etapa(self, salva) -> str | None:
        cartao = self.cartao(self.torre(), salva)
        return cartao["etapa"] if cartao else None

    # -- estrutura ----------------------------------------------------------

    def test_quatro_estagios_e_treze_etapas_na_ordem(self):
        estagios = self.torre()["estagios"]

        self.assertEqual([e["chave"] for e in estagios], ["preparar", "disputar", "contratar", "receber"])
        self.assertEqual(
            [etapa["chave"] for e in estagios for etapa in e["etapas"]],
            [
                "oportunidade",
                "cotacao",
                "cadastro_proposta",
                "disputa",
                "aguardando_julgamento",
                "julgado_habilitado",
                "aguardando_adjudicacao",
                "homologado",
                "contrato",
                "empenho",
                "entrega",
                "liquidado",
                "recebido",
            ],
        )

    # -- preparar -----------------------------------------------------------

    def test_salva_sem_cotacao_e_oportunidade_e_com_cotacao_e_cotacao(self):
        so_salva = self.salva()
        cotada = self.salva()
        self.cotar(cotada)

        self.assertEqual(self.etapa(so_salva), "oportunidade")
        self.assertEqual(self.etapa(cotada), "cotacao")

    def test_cartao_de_preparar_traz_a_salva_e_a_cotacao_para_os_modais(self):
        cotada = self.salva()
        self.cotar(cotada)
        ganha = self.salva(prazo_em_dias=-40)
        self.item(ganha, vencedor_e_a_empresa=True)

        torre = self.torre()
        cartao_cotada = self.cartao(torre, cotada)
        cartao_ganha = self.cartao(torre, ganha)

        self.assertEqual(cartao_cotada["cotacao_id"], cotada.cotacao.pk)
        self.assertEqual(cartao_cotada["salva"]["id"], cotada.pk)
        self.assertIsNone(cartao_ganha["salva"])

    def test_abrir_leva_para_a_pagina_do_fornecedor(self):
        salva = self.salva()
        salva.link_plataforma = (
            "https://cnetmobile.estaleiro.serpro.gov.br/comprasnet-web/public/compras/"
            "acompanhamento-compra?compra=92667005000562026"
        )
        salva.save()

        cartao = self.cartao(self.torre(), salva)

        self.assertEqual(
            cartao["link_plataforma"],
            "https://cnetmobile.estaleiro.serpro.gov.br/comprasnet-web/seguro/fornecedor/"
            "acompanhamento-compra?compra=92667005000562026",
        )

    def test_cartao_diz_a_compra_como_o_carlinhos_fala(self):
        """O número do pregão vem do código da compra no link do Compras.gov
        (UASG + modalidade + número + ano) — o sequencial do PNCP é outro."""

        from .torre import rotulo_da_compra

        ibama = OportunidadeSalva(
            sequencial_compra="75",
            ano_compra="2026",
            link_plataforma="https://x/acompanhamento-compra?compra=19309905001122026",
        )
        dispensa = OportunidadeSalva(
            sequencial_compra="9",
            ano_compra="2026",
            link_plataforma="https://x/acompanhamento-compra?compra=98637106000092026",
        )
        outro_portal = OportunidadeSalva(
            sequencial_compra="12", ano_compra="2026", modalidade="Concorrência - Eletrônica"
        )

        self.assertEqual(rotulo_da_compra(ibama), "Pregão 112/2026")
        self.assertEqual(rotulo_da_compra(dispensa), "Dispensa 9/2026")
        self.assertEqual(rotulo_da_compra(outro_portal), "Concorrência 12/2026")

        salva = self.salva()
        self.assertIn("compra", self.cartao(self.torre(), salva))

    def test_proposta_cadastrada_no_compras_gov_e_cadastro_de_proposta(self):
        salva = self.salva()
        self.cotar(salva)
        ParticipacaoCompra.objects.create(oportunidade=salva, fase_compra="1", proposta_cadastrada=True)

        self.assertEqual(self.etapa(salva), "cadastro_proposta")

    def test_o_pdf_da_proposta_nao_define_etapa(self):
        """O PDF é a proposta ajustada, enviada depois de ganhar: gerar o PDF
        com a cotação no prazo continua sendo a etapa Cotação."""

        from apps.propostas.models import Proposta

        salva = self.salva()
        self.cotar(salva)
        Proposta.objects.create(oportunidade=salva, valor=Decimal("100"))

        self.assertEqual(self.etapa(salva), "cotacao")

    def test_prazo_vencido_com_cotacao_e_sem_dado_do_compras_gov_espera_a_sentinela(self):
        salva = self.salva(prazo_em_dias=-2, plataforma_id="compras_gov")
        self.cotar(salva)

        cartao = self.cartao(self.torre(), salva)

        self.assertEqual(cartao["etapa"], "cadastro_proposta")
        self.assertIn("confirmar com a Sentinela", [e["texto"] for e in cartao["etiquetas"]])

    def test_prazo_vencido_com_cotacao_em_outro_portal_e_descartada(self):
        salva = self.salva(prazo_em_dias=-2, plataforma_id="")
        self.cotar(salva)

        torre = self.torre()

        self.assertIsNone(self.cartao(torre, salva))
        self.assertEqual(torre["saidas"]["descartadas"], 1)

    def test_prazo_vencido_sem_cotacao_sai_da_torre(self):
        salva = self.salva(prazo_em_dias=-2)

        torre = self.torre()

        self.assertIsNone(self.cartao(torre, salva))
        self.assertEqual(torre["saidas"]["descartadas"], 1)

    def test_participou_sem_proposta_e_descartada_caso_cubatao(self):
        salva = self.salva(prazo_em_dias=-20)
        self.cotar(salva)
        ParticipacaoCompra.objects.create(oportunidade=salva, fase_compra="4", proposta_cadastrada=False)

        torre = self.torre()

        self.assertIsNone(self.cartao(torre, salva))
        self.assertEqual(torre["saidas"]["descartadas"], 1)

    # -- disputar -----------------------------------------------------------

    def test_item_em_lances_e_disputa(self):
        salva = self.salva(prazo_em_dias=-1)
        ParticipacaoCompra.objects.create(oportunidade=salva, fase_compra="3", proposta_cadastrada=True)
        self.item(salva, fase_item="LA")

        self.assertEqual(self.etapa(salva), "disputa")

    def test_pregao_61_item_22_aguardando_julgamento(self):
        salva = self.salva(prazo_em_dias=-4)
        ParticipacaoCompra.objects.create(oportunidade=salva, fase_compra="4", proposta_cadastrada=True)
        self.item(
            salva,
            descricao="Animal Vivo",
            quantidade=Decimal("20"),
            classificacao=1,
            fase_item="E",
            anexo_solicitado="E",
            valor_proposta_inicial=Decimal("12199"),
            valor_lance_final=Decimal("11999"),
        )

        cartao = self.cartao(self.torre(), salva)

        self.assertEqual(cartao["estagio"], "disputar")
        self.assertEqual(cartao["etapa"], "aguardando_julgamento")
        item = cartao["itens"][0]
        self.assertEqual(item["classificacao"], 1)
        self.assertFalse(item["perdendo"])
        self.assertEqual(item["valor_unitario"], Decimal("11999"))
        self.assertEqual(item["valor_total"], Decimal("239980"))

    def test_pregao_56_item_22_habilitado_aguarda_adjudicacao_e_os_outros_perdem(self):
        salva = self.salva(prazo_em_dias=-46)
        ParticipacaoCompra.objects.create(oportunidade=salva, fase_compra="4", proposta_cadastrada=True)
        self.item(salva, "6", classificacao=4, fase_item="HE", valor_lance_final=Decimal("13750"))
        self.item(salva, "9", classificacao=13, fase_item="HE", quantidade=Decimal("10"))
        self.item(
            salva,
            "22",
            classificacao=1,
            fase_item="HE",
            situacao_proposta="4",
            valor_proposta_inicial=Decimal("15649"),
            valor_negociado=Decimal("15500"),
            quantidade=Decimal("1"),
        )

        cartao = self.cartao(self.torre(), salva)

        self.assertEqual(cartao["etapa"], "aguardando_adjudicacao")
        por_numero = {i["numero"]: i for i in cartao["itens"]}
        self.assertEqual(por_numero["22"]["etapa"], "aguardando_adjudicacao")
        self.assertEqual(por_numero["22"]["valor_unitario"], Decimal("15500"))
        self.assertTrue(por_numero["6"]["perdendo"])
        self.assertTrue(por_numero["9"]["perdendo"])
        self.assertEqual(cartao["valor_ganho"], Decimal("15500"))

    def test_habilitado_com_recurso_aberto_fica_em_julgado_e_habilitado(self):
        salva = self.salva(prazo_em_dias=-10)
        self.item(
            salva,
            classificacao=1,
            situacao_proposta="4",
            fase_item="AR",
            recurso_ate=self.hoje + dt.timedelta(days=3),
        )

        cartao = self.cartao(self.torre(), salva)

        self.assertEqual(cartao["etapa"], "julgado_habilitado")
        self.assertTrue(any(e["texto"].startswith("recurso até") for e in cartao["etiquetas"]))

    def test_proposta_aceita_e_julgado_e_habilitado(self):
        salva = self.salva(prazo_em_dias=-10)
        self.item(salva, classificacao=1, situacao_proposta="3", fase_item="JE")

        self.assertEqual(self.etapa(salva), "julgado_habilitado")

    def test_pregoes_112_e_201_homologados_no_pncp(self):
        ibama = self.salva(prazo_em_dias=-38, uasg="193099")
        self.item(
            ibama,
            "49",
            fonte=Fonte.PNCP,
            vencedor_e_a_empresa=True,
            homologado_em=dt.date(2026, 10, 9),
            valor_homologado=Decimal("10"),
        )

        self.assertEqual(self.etapa(ibama), "homologado")

    def test_desclassificada_em_todos_os_itens_e_encerrada(self):
        salva = self.salva(prazo_em_dias=-10)
        self.item(salva, "1", situacao_proposta="1")
        self.item(salva, "2", situacao_proposta="5")

        torre = self.torre()

        self.assertIsNone(self.cartao(torre, salva))
        self.assertEqual(torre["saidas"]["encerradas"], 1)

    def test_homologado_para_outro_fornecedor_e_encerrada(self):
        salva = self.salva(prazo_em_dias=-10)
        self.item(salva, vencedor_e_a_empresa=False, fonte=Fonte.PNCP)

        self.assertIsNone(self.cartao(self.torre(), salva))

    def test_compra_deserta_e_encerrada_e_suspensa_e_so_etiqueta(self):
        deserta = self.salva(prazo_em_dias=-10)
        ParticipacaoCompra.objects.create(oportunidade=deserta, situacao_compra="DE", proposta_cadastrada=True)
        suspensa = self.salva(prazo_em_dias=-10)
        ParticipacaoCompra.objects.create(
            oportunidade=suspensa, situacao_compra="SU", fase_compra="99", proposta_cadastrada=True
        )

        torre = self.torre()

        self.assertIsNone(self.cartao(torre, deserta))
        cartao = self.cartao(torre, suspensa)
        self.assertEqual(cartao["etapa"], "cadastro_proposta")
        self.assertIn("suspensa", [e["texto"] for e in cartao["etiquetas"]])

    # -- contratar e receber ------------------------------------------------

    def test_documentos_financeiros_levam_ate_recebido(self):
        salva = self.salva(prazo_em_dias=-60)
        item = self.item(salva, situacao_proposta="6", vencedor_e_a_empresa=True)

        DocumentoFinanceiro.objects.create(oportunidade=salva, tipo="ata", numero="ATA-1")
        self.assertEqual(self.etapa(salva), "contrato")

        DocumentoFinanceiro.objects.create(
            oportunidade=salva, item=item, tipo="empenho", numero="2026NE1", fonte=Fonte.TRANSPARENCIA
        )
        self.assertEqual(self.etapa(salva), "empenho")

        Entrega.objects.create(oportunidade=salva, data=self.hoje)
        self.assertEqual(self.etapa(salva), "entrega")

        DocumentoFinanceiro.objects.create(oportunidade=salva, tipo="liquidacao", numero="2026NS1")
        self.assertEqual(self.etapa(salva), "liquidado")

        DocumentoFinanceiro.objects.create(oportunidade=salva, tipo="pagamento", numero="2026OB1")
        self.assertEqual(self.etapa(salva), "recebido")

    def test_ordem_de_fornecimento_conta_como_empenho(self):
        salva = self.salva(prazo_em_dias=-60)
        self.item(salva, situacao_proposta="6")
        DocumentoFinanceiro.objects.create(oportunidade=salva, tipo="ordem_fornecimento", numero="OF 12")

        self.assertEqual(self.etapa(salva), "empenho")

    # -- contagens e ordem --------------------------------------------------

    def test_totais_por_etapa_e_por_estagio(self):
        a = self.salva(prazo_em_dias=-4)
        self.item(a, classificacao=1, fase_item="E")
        b = self.salva(prazo_em_dias=-46)
        self.item(b, classificacao=1, situacao_proposta="4", fase_item="HE")
        self.salva()

        estagios = {e["chave"]: e for e in self.torre()["estagios"]}

        self.assertEqual(estagios["disputar"]["total"], 2)
        etapas = {x["chave"]: x["total"] for x in estagios["disputar"]["etapas"]}
        self.assertEqual(etapas["aguardando_julgamento"], 1)
        self.assertEqual(etapas["aguardando_adjudicacao"], 1)
        self.assertEqual(estagios["preparar"]["total"], 1)

    def test_homologado_e_a_primeira_etapa_de_contratar(self):
        from .torre import ESTAGIOS

        etapas = {estagio: [chave for chave, _ in lista] for estagio, _, lista in ESTAGIOS}

        self.assertEqual(
            etapas["disputar"],
            ["disputa", "aguardando_julgamento", "julgado_habilitado", "aguardando_adjudicacao"],
        )
        self.assertEqual(etapas["contratar"], ["homologado", "contrato", "empenho"])

    def test_convocacao_em_andamento_sobe_para_o_topo(self):
        calma = self.salva(prazo_em_dias=-4)
        self.item(calma, classificacao=1, fase_item="E")
        urgente = self.salva(prazo_em_dias=-4)
        ParticipacaoCompra.objects.create(oportunidade=urgente, convocacao_em_andamento=True)
        self.item(urgente, classificacao=1, fase_item="E")

        disputar = next(e for e in self.torre()["estagios"] if e["chave"] == "disputar")

        self.assertEqual(disputar["cartoes"][0]["id"], urgente.pk)
        self.assertEqual(disputar["cartoes"][0]["etiquetas"][0]["nivel"], "alerta")

    def test_removida_da_lista_nao_aparece(self):
        salva = self.salva()
        salva.removida_em = timezone.now()
        salva.save()

        self.assertIsNone(self.cartao(self.torre(), salva))

    def test_a_tela_atual_do_ciclo_continua_igual(self):
        resposta = self.client.get("/api/licitacoes/ciclo/")

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(
            [c["etapa"] for c in resposta.data["colunas"]],
            ["oportunidade", "cotacao", "proposta", "disputa", "empenho"],
        )
