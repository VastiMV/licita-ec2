"""Cliente do Portal da Transparência (`clients/transparencia.py`)."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import httpx
from django.test import SimpleTestCase

from .clients.transparencia import (
    PortalTransparenciaClient,
    TransparenciaError,
    data_brasileira,
    valor_brasileiro,
)


def _cliente(handler, chave="chave-de-teste") -> PortalTransparenciaClient:
    cliente = PortalTransparenciaClient(chave=chave, base_url="https://api.exemplo/api-de-dados", intervalo=0)
    cliente._client = httpx.Client(
        base_url="https://api.exemplo/api-de-dados",
        headers=cliente._client.headers,
        transport=httpx.MockTransport(handler),
    )
    return cliente


class ConversoesTests(SimpleTestCase):
    def test_valor_no_formato_brasileiro(self):
        self.assertEqual(valor_brasileiro("43.945.314,38"), Decimal("43945314.38"))
        self.assertEqual(valor_brasileiro("- 2.140,82"), Decimal("-2140.82"))
        self.assertIsNone(valor_brasileiro(""))
        self.assertIsNone(valor_brasileiro("abc"))

    def test_data_no_formato_brasileiro(self):
        self.assertEqual(data_brasileira("29/07/2026"), dt.date(2026, 7, 29))
        self.assertIsNone(data_brasileira("2026-07-29"))
        self.assertIsNone(data_brasileira(None))


class PortalTransparenciaClientTests(SimpleTestCase):
    def test_pagina_ate_vir_vazio_com_a_chave_no_cabecalho(self):
        pedidos = []

        def handler(request: httpx.Request) -> httpx.Response:
            pedidos.append(request)
            pagina = int(request.url.params["pagina"])
            return httpx.Response(200, json=[{"documento": f"D{pagina}"}] if pagina <= 2 else [])

        with _cliente(handler) as cliente:
            documentos = cliente.documentos_do_favorecido("22015414000127", 1, 2026)

        self.assertEqual([d["documento"] for d in documentos], ["D1", "D2"])
        self.assertEqual(pedidos[0].url.path, "/api-de-dados/despesas/documentos-por-favorecido")
        self.assertEqual(pedidos[0].url.params["codigoPessoa"], "22015414000127")
        self.assertEqual(pedidos[0].url.params["fase"], "1")
        self.assertEqual(pedidos[0].url.params["ano"], "2026")
        self.assertEqual(pedidos[0].headers["chave-api-dados"], "chave-de-teste")

    def test_chave_recusada_vira_erro_claro(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, text="")

        with _cliente(handler) as cliente, self.assertRaises(TransparenciaError) as erro:
            cliente.documentos_do_favorecido("22015414000127", 1, 2026)
        self.assertIn("chave", str(erro.exception))
