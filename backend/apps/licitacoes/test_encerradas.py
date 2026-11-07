"""Encerradas (`/api/licitacoes/encerradas/`) — quem saiu do ciclo, por quê
e quando (ver `encerradas.py`)."""

from __future__ import annotations

import datetime as dt

from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.cotador.test_views import cotacao_payload

from .models import (
    EventoOportunidadeSalva,
    OportunidadeSalva,
    montar_texto_busca,
    registrar_prazos_vencidos,
)


class Base(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="operador@empresa.com", password="x", nome="Vasti"
        )
        self.client.force_authenticate(self.user)
        self.hoje = timezone.localdate()

    def salva(self, sequencial: str, prazo_em_dias: int | None, **extras):
        prazo = self.hoje + dt.timedelta(days=prazo_em_dias) if prazo_em_dias is not None else None
        return OportunidadeSalva.objects.create(
            cnpj_orgao="12345678000199",
            ano_compra="2026",
            sequencial_compra=sequencial,
            objeto=extras.pop("objeto", f"Edital {sequencial}"),
            uf=extras.pop("uf", "SP"),
            data_encerramento_proposta=prazo,
            **extras,
        )

    def cotar(self, salva):
        resposta = self.client.post(
            "/api/cotador/cotacoes/",
            cotacao_payload(oportunidade_id=salva.pk),
            format="json",
        )
        self.assertIn(resposta.status_code, (200, 201))

    def vencer(self, salva, dias_atras: int):
        salva.data_encerramento_proposta = self.hoje - dt.timedelta(days=dias_atras)
        salva.save(update_fields=["data_encerramento_proposta"])

    def listar(self, **params):
        resposta = self.client.get("/api/licitacoes/encerradas/", params)
        self.assertEqual(resposta.status_code, 200)
        return resposta.data

    def vencida_cotada(self, sequencial: str, dias_atras: int, **extras):
        """Encerrada de verdade: chegou a cotar e o prazo venceu."""

        salva = self.salva(sequencial, -dias_atras, **extras)
        self.cotar(salva)
        return salva

    def por_sequencial(self, dados):
        return {linha["sequencial_compra"]: linha for linha in dados["results"]}


class EncerradasTests(Base):
    """Encerradas é só quem participou do certame (disputa, empenho). Essas
    etapas ainda não existem, então hoje ela fica vazia — tudo que saiu do
    ciclo antes disso está em Descartadas (ver `test_descartadas.py`)."""

    def test_nada_que_saiu_antes_de_participar_e_encerrada(self):
        self.salva("1", 5).remover(por=self.user)  # tirada, sem cotação
        cotada_tirada = self.salva("2", 5)
        self.cotar(cotada_tirada)
        cotada_tirada.remover(por=self.user)  # tirada, com cotação
        self.salva("3", -3)  # venceu sem cotação
        self.vencida_cotada("4", 2)  # venceu com cotação

        self.assertEqual(self.listar()["count"], 0)

    def test_prazo_vencido_nao_aparece_mais_nas_salvas(self):
        self.salva("1", -1)

        salvas = self.client.get("/api/licitacoes/salvas/")

        self.assertEqual(salvas.data["count"], 0)
        self.assertEqual(self.client.get("/api/licitacoes/descartadas/").data["count"], 1)


class ProcessoTests(Base):
    """`/api/licitacoes/salvas/<id>/processo/` — o modal do processo."""

    def processo(self, salva):
        resposta = self.client.get(f"/api/licitacoes/salvas/{salva.pk}/processo/")
        self.assertEqual(resposta.status_code, 200)
        return resposta.data

    def test_eventos_ganham_etapa_e_valor_e_o_desfecho_explica(self):
        salva = self.salva("1", 5)
        salva.registrar(EventoOportunidadeSalva.Tipo.SALVA, autor=self.user, descricao="Salva.")
        self.cotar(salva)
        self.cotar(salva)
        self.vencer(salva, 1)
        registrar_prazos_vencidos()

        dados = self.processo(salva)

        tipos = [(e["tipo"], e["etapa"]) for e in dados["eventos"]]
        self.assertEqual(
            tipos,
            [
                ("oportunidade_salva", "oportunidade"),
                ("cotacao_criada", "cotacao"),
                ("cotacao_atualizada", "cotacao"),
                ("prazo_encerrado", "cotacao"),
            ],
        )
        self.assertIsNotNone(dados["eventos"][1]["valor"])
        self.assertEqual(dados["etapa"], "cotacao")
        self.assertEqual(dados["desfecho"]["tipo"], "prazo_cotacao")
        self.assertIn("A cotação estava pronta", dados["desfecho"]["porque"])

    def test_valor_de_evento_antigo_sai_do_texto(self):
        salva = self.salva("1", -2)
        salva.registrar(
            EventoOportunidadeSalva.Tipo.PROPOSTA_GERADA,
            autor=self.user,
            descricao="Cotação criada por Vasti — valor cotado R$ 2065.56.",
        )

        evento = self.processo(salva)["eventos"][0]

        self.assertEqual(evento["tipo"], "cotacao_criada")
        self.assertEqual(evento["valor"], 2065.56)

    def test_descartada_diz_quem_tirou_e_onde_estava(self):
        salva = self.salva("1", 5)
        salva.remover(por=self.user)

        desfecho = self.processo(salva)["desfecho"]

        self.assertEqual(desfecho["tipo"], "descartada")
        self.assertEqual(desfecho["por"], "Vasti")
        self.assertIn("ainda em Oportunidade", desfecho["porque"])

    def test_em_andamento_nao_tem_desfecho(self):
        self.assertIsNone(self.processo(self.salva("1", 5))["desfecho"])
