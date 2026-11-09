from types import SimpleNamespace
from unittest import mock

from rest_framework.test import APITestCase

from . import leitura

CHAVE = "chave-de-leitura-de-teste"


class ChaveDeLeituraTests(APITestCase):
    def setUp(self):
        patcher = mock.patch.object(leitura, "env", SimpleNamespace(leitura_chave=CHAVE))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_get_com_a_chave_le(self):
        resposta = self.client.get("/api/licitacoes/torre/", HTTP_X_LICITA_LEITURA_TOKEN=CHAVE)

        self.assertEqual(resposta.status_code, 200)

    def test_chave_errada_ou_ausente_nao_le(self):
        self.assertEqual(self.client.get("/api/licitacoes/torre/").status_code, 401)
        errada = self.client.get("/api/licitacoes/torre/", HTTP_X_LICITA_LEITURA_TOKEN="outra")
        self.assertEqual(errada.status_code, 401)

    def test_escrita_com_a_chave_e_recusada(self):
        for metodo in ("post", "put", "patch", "delete"):
            resposta = getattr(self.client, metodo)(
                "/api/licitacoes/salvas/1/", {}, format="json", HTTP_X_LICITA_LEITURA_TOKEN=CHAVE
            )
            self.assertEqual(resposta.status_code, 401, metodo)

    def test_desligada_sem_chave_no_servidor(self):
        with mock.patch.object(leitura, "env", SimpleNamespace(leitura_chave="")):
            resposta = self.client.get("/api/licitacoes/torre/", HTTP_X_LICITA_LEITURA_TOKEN="")
        self.assertEqual(resposta.status_code, 401)

    def test_o_leitor_nao_faz_login(self):
        self.client.get("/api/licitacoes/torre/", HTTP_X_LICITA_LEITURA_TOKEN=CHAVE)

        usuario = leitura.leitor()
        self.assertFalse(usuario.is_active)
        self.assertFalse(usuario.has_usable_password())
