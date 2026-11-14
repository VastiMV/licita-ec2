"""Testes da lista do Cotador (`/api/licitacoes/cotacoes/`).

Só as salvas com cotação e prazo aberto, cada uma com o selo e as faltas
da cotação.
"""

from __future__ import annotations

import datetime as dt

from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.cotador.test_views import cotacao_payload, item_cotado, oferta

from .models import OportunidadeSalva


class EmCotacaoTests(APITestCase):
    """A lista do Cotador (`/api/licitacoes/cotacoes/`): só a etapa Cotação,
    com o selo e as faltas de cada cotação (`apps/cotador/situacao.py`).

    O quadro antigo do Ciclo de Licitação saiu em 14/11/2026 (GEN-47); os
    testes do selo que eram dele vieram para cá."""

    def setUp(self):
        self.user = User.objects.create_user(email="operador@empresa.com", password="x")
        self.client.force_authenticate(self.user)
        self.hoje = timezone.localdate()

    def salva(self, sequencial: str, prazo_em_dias: int | None = 10, **extras):
        prazo = self.hoje + dt.timedelta(days=prazo_em_dias) if prazo_em_dias is not None else None
        return OportunidadeSalva.objects.create(
            cnpj_orgao="12345678000199",
            ano_compra="2026",
            sequencial_compra=sequencial,
            objeto=f"Edital {sequencial}",
            data_encerramento_proposta=prazo,
            **extras,
        )

    def cotar(self, salva, **overrides):
        resposta = self.client.post(
            "/api/cotador/cotacoes/",
            cotacao_payload(oportunidade_id=salva.pk, **overrides),
            format="json",
        )
        self.assertIn(resposta.status_code, (200, 201))

    def lista(self, **params):
        resposta = self.client.get("/api/licitacoes/cotacoes/", params)
        self.assertEqual(resposta.status_code, 200)
        return resposta.data

    def test_lista_so_as_com_cotacao_e_prazo_aberto(self):
        cotada = self.salva("1")
        self.cotar(cotada, itens=[item_cotado(valor_referencia="50.00")])
        self.salva("2")  # sem cotação: está em Salvas
        vencida = self.salva("3", prazo_em_dias=-1)
        self.cotar(vencida)  # prazo vencido: está em Encerradas
        removida = self.salva("4")
        self.cotar(removida)
        removida.remover()

        pagina = self.lista()

        self.assertEqual([l["id"] for l in pagina["results"]], [cotada.pk])
        linha = pagina["results"][0]
        self.assertIsNotNone(linha["cotacao_id"])
        self.assertEqual(linha["selo"]["nivel"], "ok")
        self.assertEqual(linha["selo"]["faltas"], ["gerar a proposta"])

    def test_prazo_mais_proximo_primeiro(self):
        depois = self.salva("1", prazo_em_dias=20)
        antes = self.salva("2", prazo_em_dias=5)
        self.cotar(depois)
        self.cotar(antes)

        self.assertEqual([l["id"] for l in self.lista()["results"]], [antes.pk, depois.pk])

    def selo(self, salva):
        return next(l for l in self.lista()["results"] if l["id"] == salva.pk)["selo"]

    def test_cotacao_com_item_sem_preco_aponta_a_pendencia(self):
        salva = self.salva("1")
        sem_preco = item_cotado(ofertas=[oferta(escolhida=True, custo_produto="0", frete="0")])
        self.cotar(salva, itens=[sem_preco])

        selo = self.selo(salva)

        self.assertEqual(selo["nivel"], "aviso")
        self.assertEqual(selo["faltas"], ["preço de fornecedor no item 1"])

    def test_reserva_acima_do_estimado_e_problema_e_diz_qual_item(self):
        salva = self.salva("1")
        caro = item_cotado(valor_referencia="10.00")  # custo 24,90 + frete
        self.cotar(salva, itens=[caro])

        selo = self.selo(salva)

        self.assertEqual(selo["nivel"], "alerta")
        self.assertTrue(selo["faltas"][0].startswith("item 1: reserva acima do estimado"))

    def test_prazo_amanha_vira_alerta(self):
        salva = self.salva("1", prazo_em_dias=1)
        self.cotar(salva, itens=[item_cotado(valor_referencia="50.00")])

        selo = self.selo(salva)

        self.assertEqual((selo["nivel"], selo["texto"]), ("alerta", "propostas até amanhã"))
