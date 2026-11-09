"""As propostas de todos os participantes de um item (a lista que a Sentinela
lê sozinha, sem captcha), com as respostas **reais** gravadas em 08/11/2026:

- `propostas_cubatao_item_2` — Cubatão 55/2026, item 2 (cadeira de rodas):
  31 propostas numa resposta só; a Inside em 23º, Dellamed, R$ 1.200; o 1º
  VL-Loja, Prolife, R$ 825,04; um valor absurdo de R$ 199.733,32 em 31º;
- `propostas_59_item_1` — 59/2026, item 1: a Inside **não** participa.
"""

from __future__ import annotations

import copy
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
from apps.licitacoes.models import ItemParticipado, OportunidadeSalva, PropostaDoItem
from apps.licitacoes.relatorio import relatorio_da_compra
from apps.licitacoes.torre import montar_torre
from apps.tenants.atual import tenant_atual

from . import autenticacao
from .ingestao import receber
from .ronda import INTERVALO, caminho_das_propostas, consultas

EXEMPLOS = Path(__file__).parent / "exemplos"
CNPJ = "22015414000127"
CUBATAO = "98637105000552026"
HOJE = dt.date(2026, 11, 8)


def exemplo(nome: str) -> dict:
    return json.loads((EXEMPLOS / f"{nome}.json").read_text())


def cartao(salva) -> dict | None:
    for estagio in montar_torre(hoje=HOJE)["estagios"]:
        for c in estagio["cartoes"]:
            if c["id"] == salva.pk:
                return c
    return None


class _ComCubatao(TestCase):
    def setUp(self):
        Empresa.objects.create(tenant=tenant_atual(), nome="Inside Solutions Ltda", cnpj=CNPJ)
        self.salva = OportunidadeSalva.objects.create(
            cnpj_orgao="47492806000108",
            ano_compra="2026",
            sequencial_compra="55",
            uasg="986371",
            link_plataforma=f"https://cnetmobile.estaleiro.serpro.gov.br/comprasnet-web/public/compras/acompanhamento-compra?compra={CUBATAO}",
        )
        self.item = ItemParticipado.objects.create(
            oportunidade=self.salva, numero_item="2", classificacao=23, fase_item="JR", quantidade=Decimal(1)
        )

    def receber(self, nome="propostas_cubatao_item_2", mudar=None) -> dict:
        captura = copy.deepcopy(exemplo(nome))
        if mudar:
            mudar(captura["dados"][0])
        return receber(captura["url"], captura["dados"])


class LeituraTests(_ComCubatao):
    def test_grava_as_31_propostas_e_a_linha_da_empresa(self):
        resumo = self.receber()

        self.assertEqual((resumo["tipo"], resumo["propostas"]), ("propostas_do_item", 31))
        inside = PropostaDoItem.objects.get(da_empresa=True)
        self.assertEqual((inside.classificacao, inside.marca, inside.valor_final), (23, "Dellamed", Decimal("1200")))
        primeira = PropostaDoItem.objects.get(classificacao=1)
        self.assertEqual((primeira.nome, primeira.marca), ("VL-LOJA DE VARIEDADES LTDA", "Prolife"))
        self.item.refresh_from_db()
        self.assertEqual((self.item.classificacao, self.item.marca), (23, "Dellamed"))
        self.assertIsNotNone(self.item.propostas_lidas_em)
        self.assertIsNone(self.item.vencedor_e_a_empresa)  # ainda não homologado

    def test_ler_de_novo_troca_a_lista_sem_duplicar(self):
        self.receber()
        self.receber()

        self.assertEqual(PropostaDoItem.objects.count(), 31)

    def test_item_em_que_a_empresa_nao_participa_e_ignorado(self):
        OportunidadeSalva.objects.create(
            cnpj_orgao="1", ano_compra="2026", sequencial_compra="59",
            link_plataforma="https://x/acompanhamento-compra?compra=98998305000592026",
        )  # fmt: skip

        resumo = self.receber("propostas_59_item_1")

        self.assertEqual(resumo["propostas"], 0)
        self.assertFalse(PropostaDoItem.objects.exists())

    def test_abrir_item_em_que_a_empresa_nao_entrou_nao_cria_item(self):
        """HAR de 08/11/2026: ao abrir o item 1 do 59/2026, a página pergunta a
        proposta da Inside e recebe o item **sem** proposta. Não é item dela."""

        salva = OportunidadeSalva.objects.create(
            cnpj_orgao="2", ano_compra="2026", sequencial_compra="59",
            link_plataforma="https://x/acompanhamento-compra?compra=98998305000592026",
        )  # fmt: skip
        sem_proposta = {"numero": 1, "identificador": "1", "descricao": "Laringoscópio", "fase": "HE"}
        url = (
            "https://cnetmobile.estaleiro.serpro.gov.br/comprasnet-fase-externa/v1/compras/98998305000592026"
            f"/em-selecao-fornecedores/participacoes/{CNPJ}/itens/1/propostas?filtro=1"
        )

        resumo = receber(url, [sem_proposta])

        self.assertEqual(resumo["itens"], 0)
        self.assertFalse(salva.itens_participados.exists())

    def test_homologado_para_outro_vai_para_encerradas(self):
        self.receber(mudar=lambda item: item.update(homologado=True))

        self.item.refresh_from_db()
        self.assertIs(self.item.vencedor_e_a_empresa, False)
        self.assertIsNone(cartao(self.salva))  # saiu da Torre: perdida → Encerradas

    def test_homologado_para_a_empresa_vai_para_contratar(self):
        def inside_adjudicada(item):
            item["homologado"] = True
            for p in item["propostasItem"]:
                p["situacao"] = "6" if p["participante"]["identificacao"] == CNPJ else "1"

        self.receber(mudar=inside_adjudicada)

        self.assertEqual(cartao(self.salva)["estagio"], "contratar")


class SinalTests(_ComCubatao):
    def sinal(self) -> tuple[str, int, int]:
        c = cartao(self.salva)
        return c["itens"][0]["sinal"], c["itens_ganhando"], c["itens_com_posicao"]

    def test_23o_lugar_e_perdendo(self):
        self.receber()

        self.assertEqual(self.sinal(), ("perdendo", 0, 1))

    def test_todos_na_frente_menos_um_cairam_e_o_proximo(self):
        def cairam(item):
            for p in item["propostasItem"]:
                if p["classificacao"] < 22:
                    p["situacao"] = "1"

        self.receber(mudar=cairam)

        self.assertEqual(self.sinal()[0], "proximo")

    def test_todos_na_frente_cairam_e_ganhando(self):
        def cairam(item):
            for p in item["propostasItem"]:
                if p["classificacao"] < 23:
                    p["situacao"] = "5" if p["classificacao"] % 2 else "9"

        self.receber(mudar=cairam)

        self.assertEqual(self.sinal(), ("ganhando", 1, 1))

    def test_sem_lista_vale_a_posicao_que_veio(self):
        self.item.classificacao = 2
        self.item.save()

        self.assertEqual(self.sinal()[0], "proximo")
        self.item.classificacao = 1
        self.item.save()
        self.assertEqual(self.sinal()[0], "ganhando")


class RelatorioTests(_ComCubatao):
    def test_vencedor_marca_valor_e_diferenca(self):
        self.receber()

        item = relatorio_da_compra(self.salva)["itens"][0]

        self.assertEqual(item["participantes"], 31)
        self.assertEqual(item["vencedor"]["fornecedor"], "VL-LOJA DE VARIEDADES LTDA")
        self.assertEqual((item["vencedor"]["marca"], item["vencedor"]["valor"]), ("Prolife", Decimal("825.04")))
        self.assertEqual(item["empresa"]["valor"], Decimal("1200.00"))
        self.assertEqual(item["diferenca"], Decimal("374.96"))
        self.assertEqual(item["diferenca_percentual"], Decimal("45.4"))
        self.assertEqual(item["marcas"][0]["marca"], "DELLAMED")

    def test_valor_absurdo_e_marcado_e_fica_fora_da_mediana(self):
        self.receber()

        item = relatorio_da_compra(self.salva)["itens"][0]

        atipicas = [p for p in item["propostas"] if p["atipica"]]
        self.assertEqual([p["valor"] for p in atipicas], [Decimal("199733.32")])
        self.assertLess(item["mediana"], Decimal("1200"))

    def test_sem_propostas_lidas_ainda_mostra_o_item(self):
        item = relatorio_da_compra(self.salva)["itens"][0]

        self.assertEqual((item["participantes"], item["vencedor"]), (0, None))


class RondaTests(_ComCubatao):
    def test_item_com_posicao_e_sem_leitura_entra(self):
        self.assertEqual(consultas(), [caminho_das_propostas(CUBATAO, "2")])

    def test_lido_ha_pouco_nao_entra_lido_ha_mais_de_2h_entra(self):
        self.receber()
        self.assertEqual(consultas(), [])

        ItemParticipado.objects.update(propostas_lidas_em=timezone.now() - INTERVALO - dt.timedelta(minutes=1))
        self.assertEqual(len(consultas()), 1)

    def test_item_decidido_sai_da_ronda(self):
        self.receber(mudar=lambda item: item.update(homologado=True))
        ItemParticipado.objects.update(propostas_lidas_em=timezone.now() - dt.timedelta(days=3))

        self.assertEqual(consultas(), [])

    def test_item_sem_posicao_ainda_nao_entra(self):
        ItemParticipado.objects.update(classificacao=None)

        self.assertEqual(consultas(), [])

    def test_compra_removida_nao_entra(self):
        OportunidadeSalva.objects.update(removida_em=timezone.now())

        self.assertEqual(consultas(), [])


class ApiTests(APITestCase):
    def setUp(self):
        patcher = mock.patch.object(autenticacao, "env", SimpleNamespace(sentinela_chave="chave"))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_ronda_pede_a_chave(self):
        self.assertEqual(self.client.get("/api/sentinela/ronda/").status_code, 403)
        resposta = self.client.get("/api/sentinela/ronda/", HTTP_X_SENTINELA_CHAVE="chave")
        self.assertEqual((resposta.status_code, resposta.json()), (200, {"consultas": []}))

    def test_relatorio_para_quem_esta_logado(self):
        salva = OportunidadeSalva.objects.create(cnpj_orgao="1", ano_compra="2026", sequencial_compra="5")
        url = f"/api/licitacoes/salvas/{salva.pk}/relatorio/"
        self.assertIn(self.client.get(url).status_code, (401, 403))

        self.client.force_authenticate(User.objects.create_user(email="op@empresa.com", password="x"))
        resposta = self.client.get(url)
        self.assertEqual((resposta.status_code, resposta.json()["itens"]), (200, []))


class DiagnosticoTests(_ComCubatao):
    def rodar(self, *args) -> str:
        from io import StringIO

        from django.core.management import call_command

        saida = StringIO()
        call_command("diagnostico", *args, stdout=saida)
        return saida.getvalue()

    def test_itens_suspeitos_acha_o_item_sem_proposta(self):
        ItemParticipado.objects.create(oportunidade=self.salva, numero_item="1", descricao="Laringoscópio")

        texto = self.rodar("itens-suspeitos")

        self.assertIn("Itens suspeitos (Sentinela, sem preço, sem marca, sem posição): 1", texto)
        self.assertIn("item 1 · Laringoscópio", texto)

    def test_compra_mostra_itens_e_sinal(self):
        self.receber()

        texto = self.rodar("compra", CUBATAO)

        self.assertIn("Pregão 55/2026", texto)
        self.assertIn("pos 23 (de verdade 23)", texto)
        self.assertIn("sinal perdendo · propostas 31", texto)

    def test_torre_e_sentinela_rodam(self):
        self.assertIn("Disputar (1)", self.rodar("torre"))
        self.assertIn("Notícias nas últimas 24h", self.rodar("sentinela"))
