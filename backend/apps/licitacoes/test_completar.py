"""A salva que a Sentinela trouxe sem órgão e sem itens (10/11/2026).

Caso real: Dispensa 27/2026, UASG 443034 (ração das ararinhas-azuis). A
Sentinela criou a salva com o nome do órgão vazio e `itens = []`: o cartão da
Torre mostrava o objeto no lugar do órgão e o Cotador abria sem itens, sem
deixar registrar preço. O Carlinhos tinha clicado em Salvar na busca, mas a
compra já existia — o servidor devolvia a existente sem completar nada.
"""

from __future__ import annotations

from unittest import mock

from rest_framework.test import APITestCase

from apps.accounts.models import User

from .completar import completar_as_que_faltam, completar_pelo_pncp, falta_dados
from .models import EventoOportunidadeSalva, OportunidadeSalva
from .test_salvas import item, payload

DETALHE = {
    "orgao_nome": "ICMBIO - NGI CURACA",
    "municipio_nome": "Curaçá",
    "uf": "BA",
    "objeto": "Aquisição de ração",
    "valor_total_estimado": 64800.0,
    "modalidade": "Dispensa",
    "data_publicacao": "2026-11-03",
    "situacao_nome": "Divulgada no PNCP",
}
ITENS = [
    {"numero_item": 1, "descricao_resumida": "Ração Suplementar Ave", "quantidade": 300, "valor_total": 32400.0},
    {"numero_item": 2, "descricao_resumida": "Ração Suplementar Ave", "quantidade": 300, "valor_total": 32400.0},
]


class FakePncp:
    def __init__(self, detalhe=None, itens=None):
        self.detalhe = DETALHE if detalhe is None else detalhe
        self.itens = ITENS if itens is None else itens
        self.chamadas = 0

    def detalhar_compra(self, **_):
        self.chamadas += 1
        return self.detalhe

    def listar_itens(self, **_):
        return self.itens


def da_sentinela(**campos) -> OportunidadeSalva:
    """Como `sentinela.ingestao._salva_da_compra` cria: sem órgão, sem itens."""

    base = {
        "cnpj_orgao": "08829974000194",
        "ano_compra": "2026",
        "sequencial_compra": "83",
        "objeto": "Aquisição de ração destinada à alimentação das ararinhas azuis",
        "orgao_nome": "",
        "uasg": "443034",
        "modalidade": "Dispensa - Eletrônico",
        "plataforma_id": "compras_gov",
        "link_plataforma": "https://cnetmobile.estaleiro.serpro.gov.br/comprasnet-web/public/compras/"
        "acompanhamento-compra?compra=44303406000272026",
    }
    return OportunidadeSalva.objects.create(**{**base, **campos})


class CompletarPeloPncpTests(APITestCase):
    def test_preenche_orgao_cidade_uf_valor_e_itens(self):
        salva = da_sentinela()

        campos = completar_pelo_pncp(salva, FakePncp())

        salva.refresh_from_db()
        self.assertEqual(salva.orgao_nome, "ICMBIO - NGI CURACA")
        self.assertEqual((salva.municipio, salva.uf), ("Curaçá", "BA"))
        self.assertEqual(salva.valor_total_estimado, 64800)
        self.assertEqual(len(salva.itens), 2)
        # No mesmo formato da busca: é o que o Cotador lê.
        primeiro = salva.itens[0]
        self.assertEqual(primeiro["descricao_resumida"], "Ração Suplementar Ave")
        self.assertEqual(primeiro["contratacao_orgao_nome"], "ICMBIO - NGI CURACA")
        self.assertEqual(primeiro["contratacao_cnpj_orgao"], "08829974000194")
        self.assertEqual(primeiro["plataforma_id"], "compras_gov")
        self.assertIn("compra=44303406000272026", primeiro["link_plataforma"])
        self.assertIn("RACAO SUPLEMENTAR", salva.texto_busca)
        self.assertIn("itens", campos)
        self.assertFalse(falta_dados(salva))
        evento = salva.eventos.get(tipo=EventoOportunidadeSalva.Tipo.CORRECAO)
        self.assertIn("completados pelo PNCP", evento.descricao)

    def test_nunca_troca_o_que_ja_existe(self):
        salva = da_sentinela(orgao_nome="NOME CERTO", objeto="Objeto que já estava", uf="SP")

        completar_pelo_pncp(salva, FakePncp())

        salva.refresh_from_db()
        self.assertEqual((salva.orgao_nome, salva.objeto, salva.uf), ("NOME CERTO", "Objeto que já estava", "SP"))
        self.assertEqual(len(salva.itens), 2)

    def test_completa_nao_pergunta_de_novo(self):
        salva = da_sentinela(orgao_nome="X", itens=[item()])
        pncp = FakePncp()

        self.assertEqual(completar_pelo_pncp(salva, pncp), [])
        self.assertEqual(pncp.chamadas, 0)

    def test_pncp_sem_nada_nao_grava_nem_registra(self):
        salva = da_sentinela()

        self.assertEqual(completar_pelo_pncp(salva, FakePncp(detalhe={}, itens=[])), [])
        self.assertFalse(salva.eventos.exists())

    def test_as_que_faltam_uma_com_erro_nao_para_as_outras(self):
        quebrada = da_sentinela(sequencial_compra="1")
        boa = da_sentinela(sequencial_compra="2")

        class MeioQuebrado(FakePncp):
            def detalhar_compra(self, **kw):
                if kw["sequencial"] == "1":
                    raise RuntimeError("PNCP fora do ar")
                return super().detalhar_compra(**kw)

        resumo = completar_as_que_faltam(MeioQuebrado())

        self.assertEqual(resumo, {"completadas": 1, "falhas": 1})
        boa.refresh_from_db()
        quebrada.refresh_from_db()
        self.assertEqual(boa.orgao_nome, "ICMBIO - NGI CURACA")
        self.assertEqual(quebrada.orgao_nome, "")


class SalvarDeNovoPelaBuscaTests(APITestCase):
    """O botão Salvar com a compra já na lista (a Sentinela chegou antes)."""

    def setUp(self):
        self.user = User.objects.create_user(email="carlinhos@licita.dev", password="uma-senha-forte", nome="Carlos")
        self.client.force_authenticate(self.user)
        busca = item(
            contratacao_cnpj_orgao="08829974000194",
            contratacao_sequencial_compra="83",
            contratacao_orgao_nome="ICMBIO - NGI CURACA",
            contratacao_uf="BA",
            contratacao_municipio="Curaçá",
        )
        self.payload = payload([busca, {**busca, "numero_item": "2"}])

    def test_completa_os_vazios_e_registra_quem_salvou(self):
        salva = da_sentinela()

        resposta = self.client.post("/api/licitacoes/salvas/", self.payload, format="json")

        self.assertEqual(resposta.status_code, 200)
        salva.refresh_from_db()
        self.assertEqual(salva.orgao_nome, "ICMBIO - NGI CURACA")
        self.assertEqual((salva.uf, salva.municipio), ("BA", "Curaçá"))
        self.assertEqual(len(salva.itens), 2)
        # O objeto da Sentinela continua: só o vazio é preenchido.
        self.assertIn("ararinhas", salva.objeto)
        self.assertEqual(salva.salva_por, self.user)
        self.assertEqual(salva.salva_por_nome, "Carlos")
        evento = salva.eventos.get(tipo=EventoOportunidadeSalva.Tipo.SALVA)
        self.assertIn("salva por Carlos", evento.descricao)
        self.assertIn("orgao_nome", evento.dados["campos"])

    def test_clique_repetido_nao_vira_ruido(self):
        self.client.post("/api/licitacoes/salvas/", self.payload, format="json")
        salva = OportunidadeSalva.objects.get()
        antes = salva.eventos.count()

        self.client.post("/api/licitacoes/salvas/", self.payload, format="json")

        self.assertEqual(salva.eventos.count(), antes)


class SentinelaPedeCompletarTests(APITestCase):
    def test_salva_criada_sem_dados_pede_o_pncp_depois_de_gravar(self):
        from apps.sentinela.ingestao import _salva_da_compra

        compra = {
            "chaveCompraPncp": "0882997400019410000832026",
            "numeroUasg": 443034,
            "modalidade": 6,
            "objeto": "Aquisição de ração",
        }
        with mock.patch("apps.licitacoes.tasks.completar_salva.delay") as delay:
            with self.captureOnCommitCallbacks(execute=True):
                salva, criada = _salva_da_compra(compra, codigo="44303406000272026")

        self.assertTrue(criada)
        delay.assert_called_once_with(salva.pk)

    def test_salva_completa_nao_pede_nada(self):
        from apps.sentinela.ingestao import _pedir_completar

        salva = da_sentinela(orgao_nome="ICMBIO", itens=[item()])
        with mock.patch("apps.licitacoes.tasks.completar_salva.delay") as delay:
            with self.captureOnCommitCallbacks(execute=True):
                _pedir_completar(salva)

        delay.assert_not_called()
