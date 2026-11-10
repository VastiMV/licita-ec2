"""Testes dos endpoints do cadastro de fornecedores (`/api/fornecedores/`).

Precisam de banco (`manage.py test apps.fornecedores`). O que não precisa —
dígito verificador e máscara — está em `test_documentos.py`.
"""

from __future__ import annotations

from rest_framework.test import APITestCase

from apps.accounts.models import User

from .models import Fornecedor

CNPJ_OK = "11222333000181"
OUTRO_CNPJ = "45723174000110"
CPF_OK = "52998224725"


def payload(**overrides) -> dict:
    base = {
        "nome": "Marucci Distribuidora Ltda",
        "fantasia": "Marucci",
        "tipo": "pj",
        "cnpj": "11.222.333/0001-81",
        "categoria": "materiais",
        "email": "compras@marucci.com.br",
        "uf": "SP",
        "cidade": "Campinas",
        "condicao_pagamento": "30_dias",
        "situacao": "ativo",
    }
    return {**base, **overrides}


class CadastroTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="operador@empresa.com", password="x")
        self.client.force_authenticate(self.user)

    def test_exige_autenticacao(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/fornecedores/").status_code, 401)

    def test_cadastra_e_grava_quem_cadastrou(self):
        resposta = self.client.post("/api/fornecedores/", payload(), format="json")

        self.assertEqual(resposta.status_code, 201)
        fornecedor = Fornecedor.objects.get()
        self.assertEqual(fornecedor.criado_por, self.user)

    def test_documento_e_gravado_so_com_digitos(self):
        """A máscara é da tela: quem digita com e quem digita sem tem que
        colidir na mesma restrição de unicidade."""

        self.client.post("/api/fornecedores/", payload(), format="json")
        self.assertEqual(Fornecedor.objects.get().cnpj, CNPJ_OK)

    def test_resposta_traz_o_documento_formatado_para_a_tabela(self):
        resposta = self.client.post("/api/fornecedores/", payload(), format="json")
        self.assertEqual(resposta.data["cnpj_formatado"], "11.222.333/0001-81")
        self.assertEqual(resposta.data["cidade_uf"], "Campinas / SP")

    def test_recusa_documento_invalido(self):
        resposta = self.client.post(
            "/api/fornecedores/", payload(cnpj="11.222.333/0001-82"), format="json"
        )
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("cnpj", resposta.data)

    def test_recusa_documento_repetido_dizendo_de_quem_e(self):
        self.client.post("/api/fornecedores/", payload(), format="json")

        resposta = self.client.post(
            "/api/fornecedores/", payload(nome="Outra empresa"), format="json"
        )

        self.assertEqual(resposta.status_code, 400)
        self.assertIn("Marucci Distribuidora Ltda", str(resposta.data["cnpj"]))

    def test_recusa_cpf_em_cadastro_de_pessoa_juridica(self):
        resposta = self.client.post(
            "/api/fornecedores/", payload(cnpj=CPF_OK), format="json"
        )
        self.assertEqual(resposta.status_code, 400)

    def test_aceita_cpf_quando_o_tipo_e_pessoa_fisica(self):
        resposta = self.client.post(
            "/api/fornecedores/", payload(tipo="pf", cnpj=CPF_OK), format="json"
        )
        self.assertEqual(resposta.status_code, 201)

    def test_razao_social_em_branco_e_recusada(self):
        resposta = self.client.post("/api/fornecedores/", payload(nome="   "), format="json")
        self.assertEqual(resposta.status_code, 400)

    def test_so_a_razao_social_e_obrigatoria(self):
        """Pedido da operação (10/11/2026, Jira GEN-19): no Cotador o
        Carlinhos cadastra o fornecedor que acabou de cotar por telefone, sem
        CNPJ nem e-mail. A chave do cadastro é o id, não o documento."""

        resposta = self.client.post(
            "/api/fornecedores/", {"nome": "Casa das Rações do Zé"}, format="json"
        )

        self.assertEqual(resposta.status_code, 201, resposta.data)
        fornecedor = Fornecedor.objects.get()
        self.assertEqual((fornecedor.cnpj, fornecedor.email), ("", ""))
        self.assertEqual(resposta.data["cnpj_formatado"], "")

    def test_varios_sem_documento_nao_colidem(self):
        for nome in ("Fornecedor A", "Fornecedor B"):
            resposta = self.client.post(
                "/api/fornecedores/", payload(nome=nome, cnpj="", email=""), format="json"
            )
            self.assertEqual(resposta.status_code, 201, resposta.data)
        self.assertEqual(Fornecedor.objects.filter(cnpj="").count(), 2)

    def test_documento_digitado_continua_conferido_e_sem_repetir(self):
        self.client.post("/api/fornecedores/", payload(), format="json")
        repetido = self.client.post("/api/fornecedores/", payload(nome="Outra"), format="json")
        invalido = self.client.post(
            "/api/fornecedores/", payload(cnpj="11.222.333/0001-82"), format="json"
        )
        self.assertEqual((repetido.status_code, invalido.status_code), (400, 400))

    def test_email_digitado_errado_e_recusado(self):
        resposta = self.client.post(
            "/api/fornecedores/", payload(email="sem-arroba"), format="json"
        )
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("email", resposta.data)


class ListaTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="operador@empresa.com", password="x")
        self.client.force_authenticate(self.user)

        Fornecedor.objects.create(
            nome="Alfa Materiais", cnpj=CNPJ_OK, email="a@a.com", cidade="Campinas", uf="SP"
        )
        Fornecedor.objects.create(
            nome="Beta Tecnologia",
            cnpj=OUTRO_CNPJ,
            email="b@b.com",
            categoria="tecnologia",
            cidade="Recife",
            uf="PE",
            situacao="documentacao_vencida",
        )

    def test_lista_paginada_com_a_contagem_do_conjunto(self):
        resposta = self.client.get("/api/fornecedores/")

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.data["count"], 2)
        # O aviso da tela é sobre o cadastro inteiro, não sobre a página.
        self.assertEqual(resposta.data["documentacao_vencida"], 1)

    def test_busca_casa_com_nome_cidade_categoria_e_documento(self):
        for termo, esperado in [
            ("beta", "Beta Tecnologia"),
            ("campinas", "Alfa Materiais"),
            ("Tecnologia", "Beta Tecnologia"),
            ("11.222", "Alfa Materiais"),
        ]:
            with self.subTest(termo=termo):
                resposta = self.client.get("/api/fornecedores/", {"busca": termo})
                self.assertEqual(resposta.data["count"], 1, termo)
                self.assertEqual(resposta.data["results"][0]["nome"], esperado)

    def test_ordena_pelo_nome_de_coluna_da_tabela(self):
        resposta = self.client.get("/api/fornecedores/", {"ordering": "-nome"})
        self.assertEqual(resposta.data["results"][0]["nome"], "Beta Tecnologia")

    def test_coluna_desconhecida_cai_no_padrao_em_vez_de_estourar(self):
        resposta = self.client.get("/api/fornecedores/", {"ordering": "chave_pix"})
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.data["results"][0]["nome"], "Alfa Materiais")

    def test_opcoes_do_cotador_escondem_quem_nao_pode_entrar_em_processo_novo(self):
        resposta = self.client.get("/api/fornecedores/opcoes/")

        nomes = [f["nome"] for f in resposta.data]
        self.assertEqual(nomes, ["Alfa Materiais"])

    def test_opcoes_com_todos_traz_tambem_os_vencidos(self):
        """A cotação antiga não pode perder o fornecedor que já estava
        escolhido nela."""

        resposta = self.client.get("/api/fornecedores/opcoes/", {"todos": "1"})
        self.assertEqual(len(resposta.data), 2)


class EdicaoTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="operador@empresa.com", password="x")
        self.client.force_authenticate(self.user)
        self.fornecedor = Fornecedor.objects.create(
            nome="Alfa Materiais", cnpj=CNPJ_OK, email="a@a.com"
        )

    def test_edita_o_registro_inteiro(self):
        resposta = self.client.put(
            f"/api/fornecedores/{self.fornecedor.pk}/",
            payload(nome="Alfa Materiais e Serviços", situacao="documentacao_vencida"),
            format="json",
        )

        self.assertEqual(resposta.status_code, 200)
        self.fornecedor.refresh_from_db()
        self.assertEqual(self.fornecedor.nome, "Alfa Materiais e Serviços")
        self.assertTrue(self.fornecedor.documentacao_vencida)

    def test_manter_o_proprio_documento_na_edicao_nao_e_duplicata(self):
        resposta = self.client.put(
            f"/api/fornecedores/{self.fornecedor.pk}/",
            payload(nome="Alfa Materiais"),
            format="json",
        )
        self.assertEqual(resposta.status_code, 200)

    def test_exclui(self):
        resposta = self.client.delete(f"/api/fornecedores/{self.fornecedor.pk}/")

        self.assertEqual(resposta.status_code, 204)
        self.assertFalse(Fornecedor.objects.exists())

    def test_excluir_o_que_nao_existe_devolve_404(self):
        self.assertEqual(self.client.delete("/api/fornecedores/9999/").status_code, 404)
