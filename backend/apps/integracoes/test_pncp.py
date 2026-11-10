"""Testes do `PncpClient` — transporte HTTP falso (mock), sem rede.

Portado de `tests/test_pncp_client.py` do protótipo (branch
`claude/tenta-de-novo-xu2sxb`), incluindo os testes de resiliência à
desconexão observada em 23/08/2026 (ver docs/DOMINIO.md).
"""

from __future__ import annotations

from unittest import mock

import httpx
from django.test import SimpleTestCase

from .clients import pncp as pncp_module
from .clients.pncp import PncpClient, PncpClientError, _montar_id_compra, _normalizar_edital

# Formato observado no endpoint da caixa de busca de pncp.gov.br/app/editais.
RESPOSTA_BUSCA = {
    "items": [
        {
            "id": "12345678000199-1-000005/2026",
            "doc_type": "edital",
            "title": "00005/2026",
            "description": "Aquisição de café torrado e moído para as unidades da rede municipal",
            "item_url": "/app/editais/12345678000199/2026/5",
            "orgao_cnpj": "12345678000199",
            "orgao_nome": "MUNICIPIO DE CAMPINAS",
            "unidade_codigo": "925874",
            "unidade_nome": "Prefeitura Municipal Exemplo",
            "municipio_nome": "Campinas",
            "uf": "SP",
            "numero": "00005",
            "ano": "2026",
            "numero_sequencial": "5",
            "modalidade_licitacao_id": 6,
            "modalidade_licitacao_nome": "Pregão - Eletrônico",
            "situacao_nome": "Divulgada no PNCP",
            "valor_global": 250000.0,
            "data_publicacao_pncp": "2026-08-20T10:30:00",
            "data_inicio_vigencia": "2026-08-21T00:00:00",
            "data_fim_vigencia": "2026-09-02T00:00:00",
        }
    ],
    "total": 1,
}

# Detalhe (API de consulta documentada) de uma compra publicada pelo
# Comprasnet — é o que diz a plataforma de origem e dá o link de disputa.
RESPOSTA_DETALHE_COMPRASNET = {
    "orgaoEntidade": {"cnpj": "12345678000199", "esferaId": "M"},
    "unidadeOrgao": {"ufSigla": "SP", "municipioNome": "Campinas", "codigoIbge": "3509502"},
    "usuarioNome": "Compras.gov.br",
    "linkSistemaOrigem": (
        "https://cnetmobile.estaleiro.serpro.gov.br/comprasnet-web/public/"
        "landing?destino=acompanhamento-compra&compra=92587405000052026"
    ),
}

RESPOSTA_ITENS_PNCP = [
    {
        "numeroItem": 1,
        "descricao": "CAFE TORRADO E MOIDO, EMBALAGEM 500G, TIPO TRADICIONAL",
        "quantidade": 200.0,
        "unidadeMedida": "PACOTE",
        "valorUnitarioEstimado": 18.5,
        "valorTotal": 3700.0,
        "materialOuServicoNome": "Material",
        "situacaoCompraItemNome": "Em Andamento",
        "criterioJulgamentoNome": "Menor Preço",
        "beneficioNome": "Participação exclusiva ME/EPP",
    },
    {
        "numeroItem": 2,
        "descricao": "ACUCAR CRISTAL, PACOTE 1KG",
        "quantidade": 100.0,
        "unidadeMedida": "PACOTE",
        "valorUnitarioEstimado": 4.2,
    },
]


def _pncp_falso(handler) -> PncpClient:
    client = PncpClient(base_url="https://pncp.gov.br")
    client._client = httpx.Client(base_url=client.base_url, transport=httpx.MockTransport(handler))
    return client


class PncpClientTests(SimpleTestCase):
    def test_buscar_editais_envia_a_palavra_e_normaliza(self):
        capturado = {}

        def handler(request: httpx.Request) -> httpx.Response:
            capturado["path"] = request.url.path
            capturado["params"] = dict(request.url.params)
            return httpx.Response(200, json=RESPOSTA_BUSCA)

        with _pncp_falso(handler) as client:
            editais, total = client.buscar_editais("café", uf="sp", codigo_modalidade="6")

        self.assertEqual(capturado["path"], "/api/search/")
        self.assertEqual(capturado["params"]["q"], "café")
        self.assertEqual(capturado["params"]["tipos_documento"], "edital")
        self.assertEqual(capturado["params"]["ufs"], "SP")
        self.assertEqual(capturado["params"]["modalidades"], "6")

        self.assertEqual(total, 1)
        e = editais[0]
        self.assertEqual(e["cnpj_orgao"], "12345678000199")
        self.assertEqual(e["uf"], "SP")
        self.assertEqual(e["ano_compra"], "2026")
        self.assertEqual(e["sequencial_compra"], "5")
        self.assertEqual(e["codigo_modalidade"], 6)
        self.assertIn("café", e["objeto"])
        self.assertEqual(e["data_publicacao"], "2026-08-20")  # hora removida
        self.assertEqual(e["data_encerramento_proposta"], "2026-09-02")

    def test_tam_pagina_fica_na_faixa_aceita(self):
        capturado = {}

        def handler(request: httpx.Request) -> httpx.Response:
            capturado["params"] = dict(request.url.params)
            return httpx.Response(200, json=RESPOSTA_BUSCA)

        with _pncp_falso(handler) as client:
            client.buscar_editais("café", tamanho_pagina=500)

        self.assertEqual(capturado["params"]["tam_pagina"], "50")

    def test_listar_itens_monta_o_caminho_do_orgao(self):
        capturado = {}

        def handler(request: httpx.Request) -> httpx.Response:
            capturado["path"] = request.url.path
            return httpx.Response(200, json=RESPOSTA_ITENS_PNCP)

        with _pncp_falso(handler) as client:
            itens = client.listar_itens(cnpj="12345678000199", ano="2026", sequencial="5")

        self.assertEqual(capturado["path"], "/api/pncp/v1/orgaos/12345678000199/compras/2026/5/itens")
        self.assertEqual(itens[0]["numero_item"], 1)
        self.assertIn("CAFE TORRADO", itens[0]["descricao_resumida"])
        # Sem descrição detalhada própria, a resumida preenche o campo da tela.
        self.assertEqual(itens[0]["descricao_detalhada"], itens[0]["descricao_resumida"])
        self.assertEqual(itens[0]["tipo_beneficio"], "Participação exclusiva ME/EPP")
        self.assertEqual(itens[0]["valor_unitario_estimado"], 18.5)

    def test_detalhar_compra_monta_o_caminho_documentado(self):
        capturado = {}
        resposta = {
            "orgaoEntidade": {"cnpj": "00326036000160", "esferaId": "E"},
            "unidadeOrgao": {
                "ufSigla": "SP",
                "municipioNome": "São José do Rio Preto",
                "codigoIbge": "3549805",
            },
            "usuarioNome": "Compras.gov.br",
            "linkSistemaOrigem": (
                "https://cnetmobile.estaleiro.serpro.gov.br/comprasnet-web/public/"
                "landing?destino=acompanhamento-compra&compra=92553805900672026"
            ),
        }

        def handler(request: httpx.Request) -> httpx.Response:
            capturado["path"] = request.url.path
            return httpx.Response(200, json=resposta)

        with _pncp_falso(handler) as client:
            detalhe = client.detalhar_compra(cnpj="00326036000160", ano="2026", sequencial="43")

        self.assertEqual(capturado["path"], "/api/consulta/v1/orgaos/00326036000160/compras/2026/43")
        self.assertEqual(detalhe["esfera_id"], "E")
        self.assertEqual(detalhe["uf"], "SP")
        self.assertEqual(detalhe["codigo_ibge"], "3549805")
        self.assertEqual(detalhe["municipio_nome"], "São José do Rio Preto")
        # A plataforma de origem — é daqui que o frontend tira o link certo
        # de "abrir na plataforma" (o PNCP agrega todas, ver docs/DOMINIO.md).
        self.assertEqual(detalhe["plataforma_nome"], "Compras.gov.br")
        self.assertIn("compra=92553805900672026", detalhe["link_plataforma"])

    def test_detalhar_compra_sem_orgao_ou_unidade_nao_derruba(self):
        with _pncp_falso(lambda r: httpx.Response(200, json={})) as client:
            detalhe = client.detalhar_compra(cnpj="1", ano=2026, sequencial=1)

        self.assertIsNone(detalhe["esfera_id"])
        self.assertIsNone(detalhe["codigo_ibge"])
        self.assertIsNone(detalhe["plataforma_nome"])
        self.assertIsNone(detalhe["link_plataforma"])
        self.assertIsNone(detalhe["orgao_nome"])
        self.assertIsNone(detalhe["valor_total_estimado"])

    def test_detalhar_compra_traz_o_que_completa_uma_salva(self):
        """Compra trazida pela Sentinela sem o nome do órgão (Dispensa 27/2026,
        UASG 443034, 10/11/2026): o detalhe do PNCP é de onde ele sai."""

        resposta = {
            "orgaoEntidade": {"cnpj": "08829974000194", "razaoSocial": "INSTITUTO CHICO MENDES - ICMBIO"},
            "unidadeOrgao": {"nomeUnidade": "ICMBIO - NGI CURACA", "ufSigla": "BA", "municipioNome": "Curaçá"},
            "objetoCompra": "Aquisição de ração",
            "valorTotalEstimado": 64800.0,
            "modalidadeNome": "Dispensa",
            "dataPublicacaoPncp": "2026-11-03T10:00:00",
        }
        with _pncp_falso(lambda r: httpx.Response(200, json=resposta)) as client:
            detalhe = client.detalhar_compra(cnpj="08829974000194", ano=2026, sequencial=83)

        # O nome da unidade (UASG), como na busca; a razão social é a reserva.
        self.assertEqual(detalhe["orgao_nome"], "ICMBIO - NGI CURACA")
        self.assertEqual(detalhe["objeto"], "Aquisição de ração")
        self.assertEqual(detalhe["valor_total_estimado"], 64800.0)
        self.assertEqual(detalhe["modalidade"], "Dispensa")
        self.assertEqual(detalhe["data_publicacao"], "2026-11-03")

        resposta["unidadeOrgao"].pop("nomeUnidade")
        with _pncp_falso(lambda r: httpx.Response(200, json=resposta)) as client:
            detalhe = client.detalhar_compra(cnpj="08829974000194", ano=2026, sequencial=83)
        self.assertEqual(detalhe["orgao_nome"], "INSTITUTO CHICO MENDES - ICMBIO")

    def test_listar_arquivos_monta_o_caminho_e_normaliza(self):
        capturado = {}
        resposta = [
            {
                "titulo": "Aviso 48-2026 - material de laboratorio.pdf",
                "tipoDocumentoNome": "Aviso de Contratação Direta",
                "url": "https://pncp.gov.br/pncp-api/v1/orgaos/1/compras/2026/43/arquivos/1",
            }
        ]

        def handler(request: httpx.Request) -> httpx.Response:
            capturado["path"] = request.url.path
            return httpx.Response(200, json=resposta)

        with _pncp_falso(handler) as client:
            arquivos = client.listar_arquivos(cnpj="1", ano="2026", sequencial="43")

        self.assertEqual(capturado["path"], "/api/pncp/v1/orgaos/1/compras/2026/43/arquivos")
        self.assertEqual(arquivos[0]["titulo"], "Aviso 48-2026 - material de laboratorio.pdf")
        self.assertEqual(arquivos[0]["tipo_documento"], "Aviso de Contratação Direta")
        self.assertTrue(arquivos[0]["url"].endswith("/arquivos/1"))

    def test_listar_arquivos_vazio_nao_derruba(self):
        with _pncp_falso(lambda r: httpx.Response(200, json={"detail": "sem arquivos"})) as client:
            self.assertEqual(client.listar_arquivos(cnpj="1", ano=2026, sequencial=1), [])

    def test_lista_na_raiz_tambem_e_reconhecida(self):
        """A busca devolve {"items": [...]}; a consulta devolve a lista pelada."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=RESPOSTA_ITENS_PNCP)

        with _pncp_falso(handler) as client:
            self.assertEqual(len(client.listar_itens(cnpj="1", ano=2026, sequencial=5)), 2)

    def test_erro_http_vira_mensagem_legivel(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, text="Not Found")

        with _pncp_falso(handler) as client:
            with self.assertRaises(PncpClientError) as ctx:
                client.buscar_editais("café")
            self.assertIn("404", str(ctx.exception))

    def test_resposta_html_nao_passa_por_json(self):
        """Se o portal devolver a página em vez do JSON, o erro precisa ser claro."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="<!doctype html><html>...")

        with _pncp_falso(handler) as client:
            with self.assertRaises(PncpClientError):
                client.buscar_editais("café")

    def test_id_compra_remontado_bate_com_o_da_api(self):
        """Formato real: UASG(6) + modalidade(2, tabela do compras.gov.br) +
        número(5) + ano(4) = 17 dígitos — conferido contra o
        `linkSistemaOrigem` do PNCP em 28/08/2026 (docs/DOMINIO.md). A
        modalidade chega na tabela do PNCP (6 = Pregão Eletrônico) e vira o
        código do compras.gov.br (05) dentro do id."""

        self.assertEqual(_montar_id_compra("925874", 6, "00005", "2026"), "92587405000052026")
        self.assertIsNone(_montar_id_compra(None, 6, "00005", "2026"))
        self.assertIsNone(_montar_id_compra("925874", 6, "abc", "2026"))
        # Modalidade sem equivalente no compras.gov.br (ex.: 3 = Concurso):
        # link nenhum é melhor que link quebrado.
        self.assertIsNone(_montar_id_compra("925874", 3, "00005", "2026"))
        self.assertIsNone(_montar_id_compra("925874", None, "00005", "2026"))

    def test_campos_ausentes_nao_derrubam_a_normalizacao(self):
        """O endpoint não é documentado: faltar campo é degradação, não exceção."""

        e = _normalizar_edital({"description": "Compra de café"})

        self.assertEqual(e["objeto"], "Compra de café")
        self.assertIsNone(e["cnpj_orgao"])
        self.assertIsNone(e["id_compra"])

    # --- Resiliência à desconexão observada em 23/08/2026 --------------------

    def test_manda_user_agent_de_navegador(self):
        """Sem isso o portal derruba a conexão em vez de responder."""

        capturado = {}

        def handler(request: httpx.Request) -> httpx.Response:
            capturado["ua"] = request.headers.get("user-agent", "")
            capturado["referer"] = request.headers.get("referer", "")
            return httpx.Response(200, json=RESPOSTA_BUSCA)

        with PncpClient(base_url="https://pncp.gov.br") as client:
            client._client = httpx.Client(
                base_url=client.base_url,
                headers=client._client.headers,
                transport=httpx.MockTransport(handler),
            )
            client.buscar_editais("café")

        self.assertIn("Mozilla/5.0", capturado["ua"])
        self.assertEqual(capturado["referer"], "https://pncp.gov.br/app/editais")

    def test_desconexao_transitoria_e_repetida(self):
        chamadas = []

        def handler(request: httpx.Request) -> httpx.Response:
            chamadas.append(request.url)
            if len(chamadas) == 1:
                raise httpx.RemoteProtocolError("Server disconnected without sending a response.")
            return httpx.Response(200, json=RESPOSTA_BUSCA)

        with mock.patch.object(pncp_module, "ESPERA_ENTRE_TENTATIVAS", 0):
            with _pncp_falso(handler) as client:
                editais, _ = client.buscar_editais("café")

        self.assertEqual(len(chamadas), 2)
        self.assertEqual(editais[0]["cnpj_orgao"], "12345678000199")

    def test_desconexao_persistente_vira_erro_claro(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.RemoteProtocolError("Server disconnected without sending a response.")

        with mock.patch.object(pncp_module, "ESPERA_ENTRE_TENTATIVAS", 0):
            with _pncp_falso(handler) as client:
                with self.assertRaises(PncpClientError) as ctx:
                    client.buscar_editais("café")

        self.assertIn("derrubou a conexão", str(ctx.exception))

    def test_erro_de_cliente_nao_e_repetido(self):
        """400 é resposta: repetir daria o mesmo e só atrasaria o usuário."""

        chamadas = []

        def handler(request: httpx.Request) -> httpx.Response:
            chamadas.append(request.url)
            return httpx.Response(400, text='"O filtro tipos_documento é obrigatório"')

        with mock.patch.object(pncp_module, "ESPERA_ENTRE_TENTATIVAS", 0):
            with _pncp_falso(handler) as client:
                with self.assertRaises(PncpClientError):
                    client.buscar_editais("café")

        self.assertEqual(len(chamadas), 1)

    def test_erro_5xx_transitorio_e_repetido(self):
        """O PNCP devolve 500 esporádico (pool de conexão dele estourando —
        visto ao vivo em 28/08/2026); uma repetição resolve sem mascarar
        defeito de verdade."""

        chamadas = []

        def handler(request: httpx.Request) -> httpx.Response:
            chamadas.append(request.url)
            if len(chamadas) == 1:
                return httpx.Response(500, text='{"message": "Failed to obtain JDBC Connection"}')
            return httpx.Response(200, json=RESPOSTA_BUSCA)

        with mock.patch.object(pncp_module, "ESPERA_ENTRE_TENTATIVAS", 0):
            with _pncp_falso(handler) as client:
                editais, _ = client.buscar_editais("café")

        self.assertEqual(len(chamadas), 2)
        self.assertEqual(editais[0]["cnpj_orgao"], "12345678000199")

    def test_erro_5xx_persistente_vira_erro_claro(self):
        chamadas = []

        def handler(request: httpx.Request) -> httpx.Response:
            chamadas.append(request.url)
            return httpx.Response(503, text="indisponível")

        with mock.patch.object(pncp_module, "ESPERA_ENTRE_TENTATIVAS", 0):
            with _pncp_falso(handler) as client:
                with self.assertRaises(PncpClientError) as ctx:
                    client.buscar_editais("café")

        self.assertEqual(len(chamadas), 2)
        self.assertIn("503", str(ctx.exception))
