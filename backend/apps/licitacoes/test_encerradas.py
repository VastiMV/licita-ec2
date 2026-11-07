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
    def test_so_quem_saiu_do_ciclo_aparece_com_o_motivo(self):
        self.salva("1", 5)  # no prazo: está no ciclo
        self.salva("2", None)  # sem prazo publicado: nunca vence
        self.salva("3", -3)  # venceu sem cotação
        cotada = self.salva("4", 5)
        self.cotar(cotada)
        self.vencer(cotada, 2)  # venceu com cotação
        descartada = self.salva("5", 5)
        descartada.remover(por=self.user)

        linhas = self.por_sequencial(self.listar())

        # Encerrada é só quem chegou a cotar. Venceu sem cotação (3) e
        # descartada (5) estão em Descartadas.
        self.assertEqual(sorted(linhas), ["4"])
        self.assertEqual(linhas["4"]["motivo"], "prazo_cotacao")
        self.assertEqual(linhas["4"]["motivo_label"], "Prazo perdido na cotação")
        self.assertIsNotNone(linhas["4"]["cotacao_id"])

    def test_descartada_antes_do_prazo_nao_aparece_nem_cotada(self):
        cotada = self.salva("1", 5)
        self.cotar(cotada)
        cotada.remover(por=self.user)
        self.salva("2", 5).remover(por=self.user)

        self.assertEqual(self.listar()["count"], 0)
        self.assertEqual(self.listar(motivo="descartada")["count"], 0)

    def test_cotada_tirada_da_lista_depois_do_prazo_encerrou_pelo_prazo(self):
        salva = self.vencida_cotada("1", 10)
        salva.remover(por=self.user)

        linha = self.listar()["results"][0]

        self.assertEqual(linha["motivo"], "prazo_cotacao")
        self.assertEqual(linha["encerrada_em"], str(self.hoje - dt.timedelta(days=10)))

    def test_filtra_por_periodo_motivo_uf_e_busca(self):
        self.vencida_cotada("1", 40)
        self.vencida_cotada("2", 5, uf="RJ", objeto="Cadeira de rodas")
        self.vencida_cotada("3", 3)

        periodo = self.listar(data_inicial=str(self.hoje - dt.timedelta(days=10)))
        self.assertEqual(sorted(self.por_sequencial(periodo)), ["2", "3"])

        ate = self.listar(data_final=str(self.hoje - dt.timedelta(days=30)))
        self.assertEqual(sorted(self.por_sequencial(ate)), ["1"])

        na_cotacao = self.listar(motivo="prazo_cotacao")
        self.assertEqual(sorted(self.por_sequencial(na_cotacao)), ["1", "2", "3"])

        self.assertEqual(sorted(self.por_sequencial(self.listar(uf="rj"))), ["2"])

        OportunidadeSalva.objects.filter(sequencial_compra="2").update(
            texto_busca=montar_texto_busca("Cadeira de rodas", [])
        )
        self.assertEqual(sorted(self.por_sequencial(self.listar(busca="cadeira"))), ["2"])

    def test_mais_recentes_primeiro_e_ordenacao_por_coluna(self):
        self.vencida_cotada("1", 40)
        self.vencida_cotada("2", 5)

        padrao = [linha["sequencial_compra"] for linha in self.listar()["results"]]
        self.assertEqual(padrao, ["2", "1"])

        antigas = self.listar(ordering="encerrada_em")
        self.assertEqual([linha["sequencial_compra"] for linha in antigas["results"]], ["1", "2"])

    def test_prazo_vencido_nao_aparece_mais_nas_salvas(self):
        self.salva("1", -1)

        salvas = self.client.get("/api/licitacoes/salvas/")

        self.assertEqual(salvas.data["count"], 0)
        # Sem cotação, vencida vai para Descartadas, não Encerradas.
        self.assertEqual(self.listar()["count"], 0)
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
