"""O passe da documentação (GEN-63, 10/11/2026): o site em /documentacao fica
atrás do mesmo login do Licita. O Caddy pergunta a `verificar/` a cada página
(`forward_auth`); sem passe válido, manda para a tela que pede o passe."""

from __future__ import annotations

import time
from unittest import mock

from rest_framework.test import APIClient, APITestCase

from .models import User
from .views import DOCS_COOKIE_NAME, DOCS_COOKIE_PATH

VERIFICAR = "/api/auth/documentacao/verificar/"


class PasseDaDocumentacaoTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="carlinhos@licita.dev", password="uma-senha-forte")

    def entrar(self) -> APIClient:
        cliente = APIClient(enforce_csrf_checks=True)
        resposta = cliente.post(
            "/api/auth/login/", {"email": "carlinhos@licita.dev", "password": "uma-senha-forte"}, format="json"
        )
        cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {resposta.data['access']}")
        return cliente

    def test_logado_ganha_o_passe_so_para_documentacao(self):
        cliente = self.entrar()

        resposta = cliente.post("/api/auth/documentacao/")

        self.assertEqual(resposta.status_code, 204)
        cookie = resposta.cookies[DOCS_COOKIE_NAME]
        self.assertEqual(cookie["path"], DOCS_COOKIE_PATH)
        self.assertTrue(cookie["httponly"])
        self.assertLessEqual(int(cookie["max-age"]), 12 * 3600)

    def test_sem_login_nao_ganha_passe(self):
        self.assertEqual(self.client.post("/api/auth/documentacao/").status_code, 401)

    def test_passe_valido_deixa_entrar(self):
        cliente = self.entrar()
        passe = cliente.post("/api/auth/documentacao/").cookies[DOCS_COOKIE_NAME].value

        anonimo = APIClient()
        anonimo.cookies[DOCS_COOKIE_NAME] = passe
        self.assertEqual(anonimo.get(VERIFICAR).status_code, 204)

    def test_sem_passe_manda_pedir_o_passe(self):
        resposta = self.client.get(VERIFICAR)

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta["Location"], "/abrir-documentacao")

    def test_passe_falsificado_ou_vencido_nao_entra(self):
        cliente = self.entrar()
        passe = cliente.post("/api/auth/documentacao/").cookies[DOCS_COOKIE_NAME].value

        falso = APIClient()
        falso.cookies[DOCS_COOKIE_NAME] = passe[:-3] + "abc"
        self.assertEqual(falso.get(VERIFICAR).status_code, 302)

        depois = APIClient()
        depois.cookies[DOCS_COOKIE_NAME] = passe
        with mock.patch("apps.accounts.views.time.time", return_value=time.time() + 13 * 3600):
            self.assertEqual(depois.get(VERIFICAR).status_code, 302)

    def test_usuario_desativado_perde_o_passe(self):
        cliente = self.entrar()
        passe = cliente.post("/api/auth/documentacao/").cookies[DOCS_COOKIE_NAME].value
        User.objects.filter(pk=self.user.pk).update(is_active=False)

        anonimo = APIClient()
        anonimo.cookies[DOCS_COOKIE_NAME] = passe
        self.assertEqual(anonimo.get(VERIFICAR).status_code, 302)

    def test_sair_apaga_o_passe(self):
        cliente = self.entrar()
        cliente.post("/api/auth/documentacao/")

        resposta = cliente.post("/api/auth/logout/")

        self.assertEqual(resposta.cookies[DOCS_COOKIE_NAME].value, "")
