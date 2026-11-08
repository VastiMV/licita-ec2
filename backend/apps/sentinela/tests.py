"""Testes da Sentinela com as respostas **reais** do Compras.gov.br, gravadas
na sessão do Carlinhos em 07/11/2026 (`exemplos/`, sem token nem captcha).
"""

from __future__ import annotations

import datetime as dt
import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.empresas.models import Empresa
from apps.licitacoes.models import ItemParticipado, OportunidadeSalva, ParticipacaoCompra
from apps.licitacoes.torre import montar_torre
from apps.tenants.atual import tenant_atual

from . import autenticacao
from .estado import estado_atual
from .ingestao import receber
from .models import Pulso

EXEMPLOS = Path(__file__).parent / "exemplos"
CNPJ = "22015414000127"
CHAVE = "chave-de-teste-da-sentinela"
HOJE = dt.date(2026, 11, 8)


def exemplo(nome: str) -> dict:
    return json.loads((EXEMPLOS / f"{nome}.json").read_text())


def etapa_na_torre(salva) -> str | None:
    for estagio in montar_torre(hoje=HOJE)["estagios"]:
        for cartao in estagio["cartoes"]:
            if cartao["id"] == salva.pk:
                return cartao["etapa"]
    return None


def cartao_na_torre(salva) -> dict | None:
    for estagio in montar_torre(hoje=HOJE)["estagios"]:
        for cartao in estagio["cartoes"]:
            if cartao["id"] == salva.pk:
                return cartao
    return None


class IngestaoTests(TestCase):
    def setUp(self):
        Empresa.objects.create(tenant=tenant_atual(), nome="Inside Solutions Ltda", cnpj=CNPJ)

    def receber(self, nome: str) -> dict:
        captura = exemplo(nome)
        return receber(captura["url"], captura["dados"])

    # -- participações -------------------------------------------------------

    def test_participacoes_criam_as_compras_que_o_licita_nao_conhecia(self):
        resumo = self.receber("participacoes")

        self.assertEqual(resumo["tipo"], "participacoes")
        self.assertEqual(resumo["compras"], 8)
        self.assertEqual(resumo["criadas"], 8)
        uasgs = set(OportunidadeSalva.objects.values_list("uasg", flat=True))
        self.assertTrue({"158127", "926670", "986371", "986477", "200109"} <= uasgs)

    def test_compra_criada_tem_o_link_do_compras_gov_e_o_pregao_certo(self):
        self.receber("participacoes")

        farroupilha = OportunidadeSalva.objects.get(uasg="158127")
        self.assertIn("compra=15812705000612026", farroupilha.link_plataforma)
        self.assertEqual(montar_torre(hoje=HOJE)["estagios"] and cartao_na_torre(farroupilha)["compra"], "Pregão 61/2026")

    def test_compra_ja_salva_no_licita_nao_e_duplicada(self):
        salva = OportunidadeSalva.objects.create(
            cnpj_orgao="10662072000158", ano_compra="2026", sequencial_compra="70", uasg="158127"
        )

        self.receber("participacoes")

        self.assertEqual(OportunidadeSalva.objects.filter(uasg="158127").count(), 1)
        salva.refresh_from_db()
        self.assertIn("compra=15812705000612026", salva.link_plataforma)
        self.assertEqual(salva.participacao.fase_compra, "4")

    def test_rodar_de_novo_nao_duplica(self):
        self.receber("participacoes")
        segunda = self.receber("participacoes")

        self.assertEqual(segunda["criadas"], 0)
        self.assertEqual(OportunidadeSalva.objects.count(), 8)

    def test_suspensa_e_fase_ficam_gravadas(self):
        self.receber("participacoes")

        tocantins = OportunidadeSalva.objects.get(uasg="456199").participacao
        self.assertEqual((tocantins.situacao_compra, tocantins.fase_compra), ("SU", "99"))

    def test_estar_nas_participacoes_nao_prova_proposta(self):
        """A lista de participações sozinha não diz se há proposta."""

        self.receber("participacoes")

        self.assertIsNone(OportunidadeSalva.objects.get(uasg="986371").participacao.proposta_cadastrada)

    def test_depois_da_sessao_sem_itens_lidos_fica_no_quadro_pedindo_a_leitura(self):
        self.receber("participacoes")
        pmdf = OportunidadeSalva.objects.get(uasg="926670")

        cartao = cartao_na_torre(pmdf)

        self.assertEqual(cartao["etapa"], "aguardando_julgamento")
        self.assertIn("abrir “meus itens” no Compras.gov", [e["texto"] for e in cartao["etiquetas"]])

    def test_participacao_de_uma_compra(self):
        resumo = self.receber("participacao_56")

        self.assertEqual(resumo["compras"], 1)
        pmdf = OportunidadeSalva.objects.get(uasg="926670")
        self.assertEqual(pmdf.uf, "DF")

    # -- meus itens e propostas ---------------------------------------------

    def test_meus_itens_gravam_os_itens_da_empresa_com_a_proposta(self):
        self.receber("participacoes")

        resumo = self.receber("meus_itens_56")

        self.assertEqual(resumo["itens"], 3)
        pmdf = OportunidadeSalva.objects.get(uasg="926670")
        item22 = pmdf.itens_participados.get(numero_item="22")
        self.assertEqual(item22.situacao_proposta, "4")
        self.assertEqual(item22.classificacao, 1)
        self.assertEqual(item22.fase_item, "HE")
        self.assertTrue(pmdf.participacao.proposta_cadastrada)
        item6 = pmdf.itens_participados.get(numero_item="6")
        self.assertEqual((item6.marca, item6.classificacao), ("Movement", 4))
        self.assertEqual(item6.valor_lance_final, Decimal("13750"))

    def test_pmdf_fica_em_aguardando_adjudicacao_com_o_pedido_de_desconto(self):
        self.receber("participacoes")
        self.receber("meus_itens_56")
        pmdf = OportunidadeSalva.objects.get(uasg="926670")

        cartao = cartao_na_torre(pmdf)

        self.assertEqual(cartao["etapa"], "aguardando_adjudicacao")
        perdendo = [i["numero"] for i in cartao["itens"] if i["perdendo"]]
        self.assertEqual(sorted(perdendo), ["6", "9"])
        item22 = pmdf.itens_participados.get(numero_item="22")
        self.assertEqual(item22.negociacao_texto, "Solicito um desconto para o Item 22")

    def test_negociacao_em_andamento_vira_alerta(self):
        self.receber("participacoes")
        self.receber("meus_itens_56")
        pmdf = OportunidadeSalva.objects.get(uasg="926670")
        ItemParticipado.objects.filter(oportunidade=pmdf, numero_item="22").update(negociacao="S")

        textos = [e["texto"] for e in cartao_na_torre(pmdf)["etiquetas"]]

        self.assertIn("pedido de desconto · item 22", textos)

    def test_primeira_pagina_vazia_de_meus_itens_e_participacao_sem_proposta(self):
        """Participou sem lançar preço em nenhum item → Descartadas. (O Cubatão
        foi usado aqui por engano: em 08/11/2026 o HAR mostrou que ele tem
        proposta no item 2. O teste vale para qualquer compra sem item.)"""

        self.receber("participacoes")
        cubatao = OportunidadeSalva.objects.get(uasg="986371")
        url = exemplo("meus_itens_56")["url"].replace("92667005000562026", "98637105000552026")

        receber(url, [])

        cubatao.refresh_from_db()
        self.assertFalse(cubatao.participacao.proposta_cadastrada)
        self.assertIsNone(etapa_na_torre(cubatao))

    def test_lista_de_todos_os_itens_nao_diz_o_que_e_da_empresa(self):
        self.receber("participacoes")
        url = exemplo("meus_itens_56")["url"].replace("filtro=2", "filtro=1")

        resumo = receber(url, exemplo("meus_itens_56")["dados"])

        self.assertEqual(resumo["itens"], 0)
        self.assertFalse(ItemParticipado.objects.exists())

    def test_proposta_de_um_item(self):
        self.receber("participacoes")

        resumo = self.receber("proposta_61_item_22")

        self.assertEqual(resumo["itens"], 1)
        farroupilha = OportunidadeSalva.objects.get(uasg="158127")
        item = farroupilha.itens_participados.get(numero_item="22")
        self.assertEqual((item.classificacao, item.marca), (1, "Braford"))
        self.assertEqual(item.valor_lance_final, Decimal("11999"))
        self.assertEqual(item.quantidade, Decimal("20"))
        self.assertEqual(etapa_na_torre(farroupilha), "aguardando_julgamento")

    def test_proposta_de_outro_cnpj_e_ignorada(self):
        self.receber("participacoes")
        captura = exemplo("proposta_61_item_22")

        resumo = receber(captura["url"].replace(CNPJ, "11111111000111"), captura["dados"])

        self.assertEqual(resumo["itens"], 0)

    def test_itens_de_compra_desconhecida_nao_criam_nada(self):
        resumo = self.receber("meus_itens_56")

        self.assertEqual(resumo["itens"], 0)
        self.assertFalse(OportunidadeSalva.objects.exists())

    def test_endereco_desconhecido_e_ignorado(self):
        self.assertEqual(receber("https://cnetmobile.estaleiro.serpro.gov.br/outra/coisa", {})["tipo"], "ignorado")


class EstadoTests(TestCase):
    def momento(self, texto: str) -> dt.datetime:
        return timezone.make_aware(dt.datetime.fromisoformat(texto))

    def test_nunca_falou_e_nao_instalada(self):
        self.assertEqual(estado_atual()["estado"], "nao_instalada")

    def test_falou_ha_pouco_e_ok(self):
        Pulso.objects.create()

        self.assertEqual(estado_atual()["estado"], "ok")

    def test_sessao_caiu_precisa_de_voce(self):
        Pulso.objects.create(estado=Pulso.Estado.SESSAO_CAIU)

        estado = estado_atual()

        self.assertEqual(estado["estado"], "precisa_de_voce")
        self.assertIn("sessão", estado["detalhe"])

    def test_calada_em_horario_de_trabalho_e_parada(self):
        pulso = Pulso.objects.create()
        Pulso.objects.filter(pk=pulso.pk).update(recebido_em=self.momento("2026-11-09 10:00"))

        self.assertEqual(estado_atual(self.momento("2026-11-09 10:30"))["estado"], "parada")

    def test_calada_no_fim_de_semana_e_normal(self):
        pulso = Pulso.objects.create()
        Pulso.objects.filter(pk=pulso.pk).update(recebido_em=self.momento("2026-11-06 18:00"))

        self.assertEqual(estado_atual(self.momento("2026-11-08 10:30"))["estado"], "ok")


class ApiTests(APITestCase):
    def setUp(self):
        Empresa.objects.create(tenant=tenant_atual(), nome="Inside Solutions Ltda", cnpj=CNPJ)
        patcher = mock.patch.object(autenticacao, "env", SimpleNamespace(sentinela_chave=CHAVE))
        patcher.start()
        self.addCleanup(patcher.stop)

    def post(self, rota, corpo, chave=CHAVE):
        return self.client.post(f"/api/sentinela/{rota}", corpo, format="json", HTTP_X_SENTINELA_CHAVE=chave)

    def test_sem_chave_ou_com_chave_errada_e_recusado(self):
        self.assertEqual(self.client.post("/api/sentinela/pulso/", {}, format="json").status_code, 403)
        self.assertEqual(self.post("pulso/", {}, chave="errada").status_code, 403)

    def test_sem_chave_configurada_no_servidor_recusa_tudo(self):
        with mock.patch.object(autenticacao, "env", SimpleNamespace(sentinela_chave="")):
            self.assertEqual(self.post("pulso/", {}, chave="").status_code, 403)

    def test_pulso_grava_o_estado(self):
        resposta = self.post("pulso/", {"estado": "verificacao", "versao": "0.1.0"})

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(Pulso.objects.get().estado, "verificacao")

    def test_captura_de_participacoes(self):
        resposta = self.post("captura/", {**exemplo("participacoes"), "versao": "0.1.0"})

        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertEqual(resposta.data["compras"], 8)
        self.assertEqual(Pulso.objects.get().captura, "participacoes")

    def test_captura_em_formato_inesperado_e_422(self):
        captura = exemplo("participacoes")

        resposta = self.post("captura/", {"url": captura["url"], "dados": {"mudou": True}})

        self.assertEqual(resposta.status_code, 422)

    def test_camada_de_compra_desconhecida(self):
        resposta = self.client.get(
            "/api/sentinela/camada/15812705000612026/", HTTP_X_SENTINELA_CHAVE=CHAVE
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(resposta.data["conhecida"])

    def test_camada_traz_teto_ideal_piso_custo_e_lucro_da_cotacao(self):
        from apps.cotador.models import Cotacao, ItemCotacao, OfertaFornecedor

        self.post("captura/", exemplo("participacoes"))
        salva = OportunidadeSalva.objects.get(uasg="158127")
        cotacao = Cotacao.objects.create(oportunidade=salva)
        item = ItemCotacao.objects.create(
            cotacao=cotacao, numero_item="22", descricao="Novilha", quantidade=20, valor_referencia=Decimal("12333.33")
        )
        OfertaFornecedor.objects.create(item=item, nome="Fazenda", custo_produto=Decimal("9000"), escolhida=True)

        resposta = self.client.get(
            "/api/sentinela/camada/15812705000612026/", HTTP_X_SENTINELA_CHAVE=CHAVE
        )

        self.assertTrue(resposta.data["tem_cotacao"])
        linha = resposta.data["itens"][0]
        self.assertEqual(linha["numero"], "22")
        self.assertEqual(linha["teto"], Decimal("12333.33"))
        self.assertGreater(linha["ideal"], linha["piso"])
        self.assertGreaterEqual(linha["piso"], linha["custo"])

    def test_estado_e_para_usuario_logado(self):
        self.assertEqual(self.client.get("/api/sentinela/estado/").status_code, 401)
        self.client.force_authenticate(User.objects.create_user(email="op@empresa.com", password="x"))

        resposta = self.client.get("/api/sentinela/estado/")

        self.assertEqual(resposta.data["estado"], "nao_instalada")
