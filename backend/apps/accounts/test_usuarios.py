"""Testes da tela de Usuários (`/api/usuarios/`) e do nome de autoria que
fica no registro quando o usuário é excluído."""

from __future__ import annotations

from rest_framework.test import APITestCase

from apps.fornecedores.models import Fornecedor

from .models import User

SENHA = "uma-senha-bem-forte-1"


class PermissaoTests(APITestCase):
    def test_quem_nao_e_super_usuario_recebe_403(self):
        comum = User.objects.create_user(email="comum@x.com", password=SENHA, nome="Comum")
        self.client.force_authenticate(comum)

        self.assertEqual(self.client.get("/api/usuarios/").status_code, 403)
        self.assertEqual(self.client.get("/api/armazenamento/config/").status_code, 403)

    def test_staff_sem_super_usuario_nao_entra_mais(self):
        staff = User.objects.create_user(email="staff@x.com", password=SENHA, is_staff=True)
        self.client.force_authenticate(staff)

        self.assertEqual(self.client.get("/api/usuarios/").status_code, 403)


class CadastroTests(APITestCase):
    def setUp(self):
        self.eu = User.objects.create_user(
            email="eu@x.com", password=SENHA, nome="Gustavo", is_superuser=True, is_staff=True
        )
        self.client.force_authenticate(self.eu)

    def test_cadastra_e_a_senha_nao_volta(self):
        resposta = self.client.post(
            "/api/usuarios/",
            {"nome": "Vasti", "email": "Vasti@X.com", "senha": SENHA, "is_superuser": True},
        )

        self.assertEqual(resposta.status_code, 201, resposta.data)
        self.assertNotIn("senha", resposta.data)
        criado = User.objects.get(pk=resposta.data["id"])
        self.assertTrue(criado.check_password(SENHA))
        self.assertTrue(criado.is_superuser)
        self.assertTrue(criado.is_staff)

    def test_cadastro_sem_senha_e_recusado(self):
        resposta = self.client.post("/api/usuarios/", {"nome": "A", "email": "a@x.com"})

        self.assertEqual(resposta.status_code, 400)
        self.assertIn("senha", resposta.data)

    def test_email_repetido_sem_diferenciar_maiuscula(self):
        resposta = self.client.post(
            "/api/usuarios/", {"nome": "Outro", "email": "EU@x.com", "senha": SENHA}
        )

        self.assertEqual(resposta.status_code, 400)
        self.assertIn("email", resposta.data)

    def test_editar_com_senha_em_branco_mantem_a_atual(self):
        outro = User.objects.create_user(email="o@x.com", password=SENHA, nome="O")

        resposta = self.client.put(
            f"/api/usuarios/{outro.pk}/",
            {"nome": "Outro Nome", "email": "o@x.com", "senha": "", "is_superuser": False},
        )

        self.assertEqual(resposta.status_code, 200, resposta.data)
        outro.refresh_from_db()
        self.assertEqual(outro.nome, "Outro Nome")
        self.assertTrue(outro.check_password(SENHA))

    def test_nao_tira_de_si_mesmo_o_super_usuario(self):
        resposta = self.client.put(
            f"/api/usuarios/{self.eu.pk}/",
            {"nome": "Gustavo", "email": "eu@x.com", "is_superuser": False},
        )

        self.assertEqual(resposta.status_code, 400)
        self.assertIn("is_superuser", resposta.data)

    def test_nao_exclui_a_si_mesmo(self):
        self.assertEqual(self.client.delete(f"/api/usuarios/{self.eu.pk}/").status_code, 400)

    def test_busca_por_nome_ou_email(self):
        User.objects.create_user(email="vasti@x.com", password=SENHA, nome="Vasti")

        resposta = self.client.get("/api/usuarios/", {"busca": "vast"})

        self.assertEqual([u["email"] for u in resposta.data["results"]], ["vasti@x.com"])


class HistoricoSobreviveTests(APITestCase):
    def test_excluir_usuario_mantem_o_nome_no_registro(self):
        admin = User.objects.create_user(
            email="adm@x.com", password=SENHA, is_superuser=True, is_staff=True
        )
        autor = User.objects.create_user(email="autor@x.com", password=SENHA, nome="Autor")
        fornecedor = Fornecedor.objects.create(
            nome="F", cnpj="11222333000181", email="f@x.com", criado_por=autor
        )
        self.assertEqual(fornecedor.criado_por_nome, "Autor")

        self.client.force_authenticate(admin)
        self.assertEqual(self.client.delete(f"/api/usuarios/{autor.pk}/").status_code, 204)

        fornecedor.refresh_from_db()
        self.assertIsNone(fornecedor.criado_por)
        self.assertEqual(fornecedor.criado_por_nome, "Autor")


class PerfilTests(APITestCase):
    def setUp(self):
        self.eu = User.objects.create_user(email="comum@x.com", password=SENHA, nome="Comum")
        self.client.force_authenticate(self.eu)

    def test_quem_nao_e_super_usuario_edita_o_proprio_perfil(self):
        resposta = self.client.put(
            "/api/usuarios/eu/",
            {"nome": "Novo Nome", "email": "comum@x.com", "senha": "outra-senha-forte-2"},
        )

        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.eu.refresh_from_db()
        self.assertEqual(self.eu.nome, "Novo Nome")
        self.assertTrue(self.eu.check_password("outra-senha-forte-2"))

    def test_nao_vira_super_usuario_pelo_perfil(self):
        self.client.put(
            "/api/usuarios/eu/",
            {"nome": "Comum", "email": "comum@x.com", "is_superuser": True},
        )

        self.eu.refresh_from_db()
        self.assertFalse(self.eu.is_superuser)
        self.assertFalse(self.eu.is_staff)


class FotoTests(APITestCase):
    """Cada um sobe a própria foto (pedido da operação, 08/11/2026)."""

    PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

    def setUp(self):
        self.usuario = User.objects.create_user(email="vasti@inside.com", password="x", nome="Vasti")
        self.client.force_authenticate(self.usuario)

    def test_troca_e_tira_a_propria_foto(self):
        resposta = self.client.put("/api/usuarios/eu/foto/", {"foto": self.PNG}, format="json")

        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertEqual(self.client.get("/api/usuarios/eu/").data["foto"], self.PNG)

        self.client.delete("/api/usuarios/eu/foto/")
        self.assertEqual(self.client.get("/api/usuarios/eu/").data["foto"], "")

    def test_so_aceita_imagem(self):
        for invalida in ("data:text/html;base64,PGgxPg==", "https://exemplo.com/foto.png", "javascript:alert(1)"):
            resposta = self.client.put("/api/usuarios/eu/foto/", {"foto": invalida}, format="json")
            self.assertEqual(resposta.status_code, 400, invalida)

    def test_foto_grande_demais_e_recusada(self):
        enorme = "data:image/png;base64," + "A" * 500_000

        self.assertEqual(self.client.put("/api/usuarios/eu/foto/", {"foto": enorme}, format="json").status_code, 400)

    def test_foto_nao_vai_na_lista_de_usuarios(self):
        self.usuario.is_superuser = True
        self.usuario.save()
        self.client.put("/api/usuarios/eu/foto/", {"foto": self.PNG}, format="json")

        lista = self.client.get("/api/usuarios/").data
        linhas = lista["results"] if isinstance(lista, dict) else lista
        self.assertNotIn("foto", linhas[0])

    def test_perfil_nao_muda_a_foto_pelo_put_geral(self):
        self.client.put(
            "/api/usuarios/eu/",
            {"nome": "Vasti", "email": "vasti@inside.com", "foto": self.PNG},
            format="json",
        )

        self.assertEqual(User.objects.get(pk=self.usuario.pk).foto, "")
