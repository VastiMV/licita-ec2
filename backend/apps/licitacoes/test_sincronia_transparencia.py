"""Testes da sincronia com o Portal da Transparência (`sincronia_transparencia.py`)
e das rotas de documentos que vieram sem licitação.

Os registros seguem o formato real da API (conferido em 07/11/2026): data em
"dd/mm/aaaa", valor em "1.234,56", `documento` como código completo e o
processo em `numeroProcesso` — ou só citado na observação do pagamento.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from django.test import TestCase
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.empresas.models import Empresa
from apps.integracoes.clients.transparencia import TransparenciaError
from apps.tenants.atual import tenant_atual

from . import sincronia_transparencia
from .models import DocumentoFinanceiro, Fonte, ItemParticipado, OportunidadeSalva
from .sincronia_transparencia import sincronizar_transparencia
from .torre import montar_torre

CNPJ = "22015414000127"
HOJE = dt.date(2026, 11, 20)


def documento(fase: str, codigo: str, valor: str, ug: str, processo: str = "", observacao: str = "", data="18/11/2026"):
    return {
        "data": data,
        "documento": codigo,
        "documentoResumido": codigo[-12:],
        "observacao": observacao,
        "valor": valor,
        "codigoUg": ug,
        "ug": "UG",
        "orgao": "Órgão",
        "numeroProcesso": processo,
        "fase": fase,
        "codigoFavorecido": "22.015.414/0001-27",
    }


class ClienteFalso:
    def __init__(self, por_fase=None, erro=None):
        self.por_fase = por_fase or {}
        self.erro = erro
        self.consultas = []

    def documentos_do_favorecido(self, cnpj, fase, ano):
        self.consultas.append((cnpj, fase, ano))
        if self.erro:
            raise self.erro
        return [d for d in self.por_fase.get(fase, []) if int(d["data"][-4:]) == ano]


class SincroniaTransparenciaTests(TestCase):
    def setUp(self):
        Empresa.objects.create(tenant=tenant_atual(), nome="Inside Solutions Ltda", cnpj=CNPJ)
        self.ibama = self.ganha("193099", "75", "02001.015536/2024-21")
        self.ufvjm = self.ganha("153036", "41", "23086011683202671")

    def ganha(self, uasg, sequencial, processo) -> OportunidadeSalva:
        salva = OportunidadeSalva.objects.create(
            cnpj_orgao=f"{uasg}00000000",
            ano_compra="2026",
            sequencial_compra=sequencial,
            uasg=uasg,
            numero_processo=processo,
            plataforma_id="compras_gov",
            data_encerramento_proposta=dt.date(2026, 9, 30),
        )
        ItemParticipado.objects.create(oportunidade=salva, numero_item="1", vencedor_e_a_empresa=True, fonte=Fonte.PNCP)
        return salva

    def rodar(self, cliente) -> dict:
        return sincronizar_transparencia(hoje=HOJE, cliente=cliente)

    def etapa(self, salva):
        for estagio in montar_torre(hoje=HOJE)["estagios"]:
            for cartao in estagio["cartoes"]:
                if cartao["id"] == salva.pk:
                    return cartao["etapa"]
        return None

    def test_empenho_com_o_mesmo_processo_liga_a_licitacao(self):
        empenho = documento("Empenho", "193099192082026NE000101", "53.312,08", "999999", "02001.015536/2024-21")

        resumo = self.rodar(ClienteFalso({1: [empenho]}))

        doc = DocumentoFinanceiro.objects.get()
        self.assertEqual(doc.tipo, "empenho")
        self.assertEqual(doc.fonte, Fonte.TRANSPARENCIA)
        self.assertEqual(doc.oportunidade, self.ibama)
        self.assertEqual(doc.valor, Decimal("53312.08"))
        self.assertEqual(doc.data, dt.date(2026, 11, 18))
        self.assertEqual(doc.dados["ligado_por"], "processo")
        self.assertEqual(resumo["ligados"], 1)
        self.assertEqual(self.etapa(self.ibama), "empenho")

    def test_processo_com_outro_formato_ainda_liga(self):
        empenho = documento("Empenho", "153036152292026NE000044", "14.500,00", "000000", "23086.011683/2026-71")

        self.rodar(ClienteFalso({1: [empenho]}))

        self.assertEqual(DocumentoFinanceiro.objects.get().oportunidade, self.ufvjm)

    def test_sem_processo_liga_pela_unidade_quando_ha_uma_licitacao_so(self):
        empenho = documento("Empenho", "193099192082026NE000102", "1.000,00", "193099")

        self.rodar(ClienteFalso({1: [empenho]}))

        doc = DocumentoFinanceiro.objects.get()
        self.assertEqual(doc.oportunidade, self.ibama)
        self.assertEqual(doc.dados["ligado_por"], "unidade")

    def test_duas_licitacoes_na_mesma_unidade_sem_processo_fica_sem_licitacao(self):
        self.ganha("193099", "80", "")
        empenho = documento("Empenho", "193099192082026NE000103", "1.000,00", "193099")

        resumo = self.rodar(ClienteFalso({1: [empenho]}))

        self.assertIsNone(DocumentoFinanceiro.objects.get().oportunidade)
        self.assertEqual(resumo["sem_licitacao"], 1)

    def test_pagamento_com_o_processo_so_na_observacao_leva_a_recebido(self):
        empenho = documento("Empenho", "153036152292026NE000044", "14.500,00", "153036", "23086011683202671")
        liquidacao = documento("Liquidação", "153036152292026NS000201", "14.500,00", "153036", "23086011683202671")
        pagamento = documento(
            "Pagamento",
            "153036152292026OB000301",
            "14.500,00",
            "000000",
            observacao="PAGAMENTO NF 345 - PROCESSO: 23086.011683/2026-71.",
        )

        self.rodar(ClienteFalso({1: [empenho], 2: [liquidacao], 3: [pagamento]}))

        tipos = sorted(self.ufvjm.documentos_financeiros.values_list("tipo", flat=True))
        self.assertEqual(tipos, ["empenho", "liquidacao", "pagamento"])
        self.assertEqual(self.etapa(self.ufvjm), "recebido")

    def test_rodar_duas_vezes_nao_duplica(self):
        cliente = ClienteFalso({1: [documento("Empenho", "193099192082026NE000101", "10,00", "193099")]})

        self.rodar(cliente)
        self.rodar(cliente)

        self.assertEqual(DocumentoFinanceiro.objects.count(), 1)

    def test_ligacao_feita_a_mao_nao_e_desfeita(self):
        cliente = ClienteFalso({1: [documento("Empenho", "193099192082026NE000101", "10,00", "000000")]})
        self.rodar(cliente)
        doc = DocumentoFinanceiro.objects.get()
        self.assertIsNone(doc.oportunidade)
        doc.oportunidade = self.ufvjm
        doc.save()

        self.rodar(cliente)

        self.assertEqual(DocumentoFinanceiro.objects.get().oportunidade, self.ufvjm)

    def test_estorno_negativo_e_guardado_com_sinal(self):
        self.rodar(ClienteFalso({3: [documento("Pagamento", "193099192082026OB000999", "- 2.140,82", "193099")]}))

        self.assertEqual(DocumentoFinanceiro.objects.get().valor, Decimal("-2140.82"))

    def test_consulta_o_ano_atual_e_o_anterior_nas_tres_fases(self):
        cliente = ClienteFalso()

        self.rodar(cliente)

        self.assertEqual(
            sorted(cliente.consultas),
            sorted((CNPJ, fase, ano) for fase in (1, 2, 3) for ano in (2025, 2026)),
        )

    def test_sem_chave_nao_consulta_e_avisa(self):
        with mock.patch.object(sincronia_transparencia, "env", SimpleNamespace(portal_transparencia_chave="")):
            resumo = sincronizar_transparencia(hoje=HOJE)

        self.assertTrue(resumo["sem_chave"])
        self.assertFalse(DocumentoFinanceiro.objects.exists())

    def test_erro_do_portal_nao_derruba_e_fica_no_resumo(self):
        resumo = self.rodar(ClienteFalso(erro=TransparenciaError("recusou a chave")))

        self.assertIn("recusou a chave", resumo["erro"])

    def test_agendada_as_8h10_de_segunda_a_sexta(self):
        from django_celery_beat.models import PeriodicTask

        tarefa = PeriodicTask.objects.get(task="licitacoes.sincronizar_transparencia")

        self.assertEqual((tarefa.crontab.minute, tarefa.crontab.hour), ("10", "8"))
        self.assertEqual(tarefa.crontab.day_of_week, "1-5")


class DocumentosSemLicitacaoTests(APITestCase):
    def setUp(self):
        self.client.force_authenticate(User.objects.create_user(email="op@empresa.com", password="x"))
        self.salva = OportunidadeSalva.objects.create(cnpj_orgao="1", ano_compra="2026", sequencial_compra="1")
        ItemParticipado.objects.create(oportunidade=self.salva, numero_item="49", vencedor_e_a_empresa=True)
        self.solto = DocumentoFinanceiro.objects.create(
            tipo="empenho", numero="193099192082026NE000103", fonte=Fonte.TRANSPARENCIA, valor=Decimal("10")
        )

    def test_lista_os_documentos_sem_licitacao(self):
        resposta = self.client.get("/api/licitacoes/documentos-financeiros/sem-licitacao/")

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual([d["id"] for d in resposta.data], [self.solto.pk])

    def test_ligar_a_uma_licitacao_e_item(self):
        resposta = self.client.post(
            f"/api/licitacoes/documentos-financeiros/{self.solto.pk}/ligar/",
            {"oportunidade_id": self.salva.pk, "item_numero": "49"},
            format="json",
        )

        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.solto.refresh_from_db()
        self.assertEqual(self.solto.oportunidade, self.salva)
        self.assertEqual(self.solto.item.numero_item, "49")
        self.assertEqual(self.client.get("/api/licitacoes/documentos-financeiros/sem-licitacao/").data, [])

    def test_ligar_a_licitacao_inexistente_e_400(self):
        resposta = self.client.post(
            f"/api/licitacoes/documentos-financeiros/{self.solto.pk}/ligar/",
            {"oportunidade_id": 999999},
            format="json",
        )

        self.assertEqual(resposta.status_code, 400)
