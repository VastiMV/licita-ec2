"""Testes do `ComprasGovClient` — transporte HTTP falso (mock), sem rede.

Portado de `tests/test_compras_gov_client.py` do protótipo (branch
`claude/tenta-de-novo-xu2sxb`), formato real do envelope confirmado contra a
API (ver docs/DOMINIO.md).
"""

from __future__ import annotations

import httpx
from django.test import SimpleTestCase

from .clients.compras_gov import (
    ComprasGovClient,
    ComprasGovClientError,
    montar_link_compras_gov,
    montar_link_pncp,
    normalizar,
)

# O `idCompra` real tem 17 dígitos: UASG(6) + modalidade(2, tabela do próprio
# compras.gov.br — 05 = Pregão Eletrônico) + número(5) + ano(4). Conferido
# contra a API real em 28/08/2026 (docs/DOMINIO.md).
RESPOSTA_CONTRATACOES = {
    "resultado": [
        {
            "idCompra": "92587405000052026",
            "numeroControlePNCP": "12345678000199-1-000005/2026",
            "unidadeOrgaoCodigoUnidade": "925874",
            "unidadeOrgaoNomeUnidade": "Prefeitura Municipal Exemplo",
            "orgaoEntidadeCnpj": "12345678000199",
            "unidadeOrgaoUfSigla": "SP",
            "unidadeOrgaoMunicipioNome": "Campinas",
            "numeroCompra": "00005",
            "anoCompraPncp": 2026,
            "sequencialCompraPncp": 5,
            "modalidadeNome": "Pregão - Eletrônico",
            # Tabela do compras.gov.br (MODALIDADES_CONTRATACOES): 5 = Pregão
            # Eletrônico — coerente com o "05" embutido no idCompra acima.
            "codigoModalidade": 5,
            "objetoCompra": "Aquisição de equipamentos de informática",
            "situacaoCompraNomePncp": "Divulgada no PNCP",
            "srp": True,
            "valorTotalEstimado": 250000.0,
            "dataPublicacaoPncp": "2026-08-20 10:30:00",
            "dataAberturaPropostaPncp": "2026-08-21 09:00:00",
            "dataEncerramentoPropostaPncp": "2026-09-02 09:00:00",
        }
    ],
    "totalRegistros": 1,
    "totalPaginas": 1,
    "paginasRestantes": 0,
}

RESPOSTA_ITENS = {
    "resultado": [
        {
            "idCompraItem": "92587405000052026-1",
            "numeroItemCompra": 1,
            "descricaoResumida": "Notebook",
            "descricaodetalhada": "Notebook com processador de 8 núcleos, 16GB RAM, SSD 512GB, tela 14 polegadas",
            "materialOuServicoNome": "Material",
            "quantidade": 50.0,
            "unidadeMedida": "UNIDADE",
            "valorUnitarioEstimado": 4500.0,
            "valorTotal": 225000.0,
            "situacaoCompraItemNome": "Em Andamento",
            "criterioJulgamentoNome": "Menor Preço",
            "tipoBeneficioNome": "Sem benefício",
            "temResultado": False,
        }
    ],
    "totalPaginas": 1,
}


def _client_falso(handler) -> ComprasGovClient:
    client = ComprasGovClient(base_url="https://dadosabertos.compras.gov.br")
    client._client = httpx.Client(base_url=client.base_url, transport=httpx.MockTransport(handler))
    return client


class ComprasGovClientTests(SimpleTestCase):
    def test_buscar_contratacoes_normaliza_campos(self):
        capturado = {}

        def handler(request: httpx.Request) -> httpx.Response:
            capturado["params"] = dict(request.url.params)
            return httpx.Response(200, json=RESPOSTA_CONTRATACOES)

        with _client_falso(handler) as client:
            contratacoes, total_paginas = client.buscar_contratacoes(
                data_publicacao_inicial="2026-08-01",
                data_publicacao_final="2026-08-23",
                codigo_modalidade="6",
                uf="sp",
            )

        # Os três parâmetros obrigatórios da API precisam ser enviados.
        self.assertEqual(capturado["params"]["dataPublicacaoPncpInicial"], "2026-08-01")
        self.assertEqual(capturado["params"]["dataPublicacaoPncpFinal"], "2026-08-23")
        self.assertEqual(capturado["params"]["codigoModalidade"], "6")
        self.assertEqual(capturado["params"]["unidadeOrgaoUfSigla"], "SP")

        self.assertEqual(total_paginas, 1)
        c = contratacoes[0]
        self.assertEqual(c["id_compra"], "92587405000052026")
        self.assertEqual(c["uasg"], "925874")
        self.assertEqual(c["uf"], "SP")
        self.assertEqual(c["data_publicacao"], "2026-08-20")  # hora removida

    def test_listar_itens_usa_tipo_id_compra(self):
        capturado = {}

        def handler(request: httpx.Request) -> httpx.Response:
            capturado["params"] = dict(request.url.params)
            return httpx.Response(200, json=RESPOSTA_ITENS)

        with _client_falso(handler) as client:
            itens = client.listar_itens("92587405000052026")

        self.assertEqual(capturado["params"]["tipo"], "idCompra")
        self.assertEqual(capturado["params"]["codigo"], "92587405000052026")

        item = itens[0]
        self.assertEqual(item["numero_item"], 1)
        self.assertIn("16GB RAM", item["descricao_detalhada"])
        self.assertEqual(item["quantidade"], 50.0)

    def test_erro_http_vira_mensagem_legivel(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, text="Resource Not Found")

        with _client_falso(handler) as client:
            with self.assertRaises(ComprasGovClientError) as ctx:
                client.buscar_contratacoes(
                    data_publicacao_inicial="2026-08-01",
                    data_publicacao_final="2026-08-23",
                    codigo_modalidade="6",
                )
            self.assertIn("404", str(ctx.exception))

    def test_links(self):
        contratacao = {
            "id_compra": "92587405000052026",
            "cnpj_orgao": "12345678000199",
            "ano_compra": 2026,
            "sequencial_compra": 5,
        }
        self.assertIn("compra=92587405000052026", montar_link_compras_gov(contratacao))
        self.assertEqual(
            montar_link_pncp(contratacao), "https://pncp.gov.br/app/editais/12345678000199/2026/5"
        )
        self.assertIsNone(montar_link_pncp({"id_compra": "x"}))
        # Sem idCompra não há link — melhor que um botão que abre 404.
        self.assertIsNone(montar_link_compras_gov({}))

    def test_normalizar_tira_acento_e_sobe_caixa(self):
        self.assertEqual(normalizar("café"), "CAFE")
        self.assertEqual(normalizar(" Papel A4 "), "PAPEL A4")

    def test_listar_pdms_normaliza_e_devolve_total_de_paginas(self):
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(dict(request.url.params)["tamanhoPagina"], "500")
            return httpx.Response(
                200,
                json={
                    "resultado": [
                        {
                            "codigoPdm": 281,
                            "nomePdm": "CARTUCHO CANETA TINTEIRO",
                            "codigoClasse": 75,
                            "nomeClasse": "Material escritório",
                            "codigoGrupo": 7,
                            "nomeGrupo": "Escritório",
                        }
                    ],
                    "totalPaginas": 41,
                },
            )

        with _client_falso(handler) as client:
            pdms, total_paginas = client.listar_pdms(pagina=1, tamanho_pagina=500)

        self.assertEqual(total_paginas, 41)
        self.assertEqual(pdms[0]["codigo_pdm"], 281)
        self.assertEqual(pdms[0]["nome_pdm"], "CARTUCHO CANETA TINTEIRO")

    def test_tamanho_pagina_e_limitado_a_faixa_aceita_pela_api(self):
        # A API devolve HTTP 400 fora da faixa 10..500.
        capturado = {}

        def handler(request: httpx.Request) -> httpx.Response:
            capturado["tam"] = dict(request.url.params)["tamanhoPagina"]
            return httpx.Response(200, json={"resultado": [], "totalPaginas": 1})

        with _client_falso(handler) as client:
            client.listar_pdms(tamanho_pagina=3)
            self.assertEqual(capturado["tam"], "10")
            client.listar_pdms(tamanho_pagina=9000)
            self.assertEqual(capturado["tam"], "500")

    def test_buscar_itens_por_pdm_envia_codigo_pdm_e_datas(self):
        capturado = {}

        def handler(request: httpx.Request) -> httpx.Response:
            capturado["params"] = dict(request.url.params)
            return httpx.Response(200, json={"resultado": [{"idCompra": "X", "numeroItemCompra": 1}]})

        with _client_falso(handler) as client:
            itens = client.buscar_itens_por_pdm(
                codigo_pdm=999, data_inicial="2026-07-01", data_final="2026-09-30"
            )

        self.assertEqual(capturado["params"]["codigoPdm"], "999")
        self.assertEqual(capturado["params"]["dataInclusaoPncpInicial"], "2026-07-01")
        self.assertEqual(itens[0]["id_compra"], "X")


class ResultadosEAtasDoFornecedorTests(SimpleTestCase):
    """Os dois métodos da sincronia com o PNCP (apps/licitacoes/sincronia_pncp.py)."""

    def test_resultados_percorre_todas_as_paginas_com_o_cnpj_e_as_datas(self):
        paginas = []

        def handler(request: httpx.Request) -> httpx.Response:
            params = dict(request.url.params)
            params["caminho"] = request.url.path
            paginas.append(params)
            pagina = int(params["pagina"])
            return httpx.Response(
                200,
                json={"resultado": [{"numeroItemPncp": pagina}], "paginasRestantes": 2 - pagina},
            )

        with _client_falso(handler) as client:
            registros = client.resultados_do_fornecedor("22015414000127", "2025-11-08", "2026-11-07")

        self.assertEqual([r["numeroItemPncp"] for r in registros], [1, 2])
        self.assertEqual(paginas[0]["niFornecedor"], "22015414000127")
        self.assertEqual(paginas[0]["dataResultadoPncpInicial"], "2025-11-08")
        self.assertEqual(paginas[0]["dataResultadoPncpFinal"], "2026-11-07")
        self.assertEqual(paginas[0]["caminho"], "/modulo-contratacoes/3_consultarResultadoItensContratacoes_PNCP_14133")

    def test_404_do_modulo_e_lista_vazia_e_nao_erro(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, json={"statusCode": 404, "message": "Resource not found"})

        with _client_falso(handler) as client:
            self.assertEqual(client.itens_de_ata_do_fornecedor("22015414000127", "2025-11-08", "2026-11-07"), [])

    def test_atas_usam_o_modulo_arp_com_vigencia(self):
        capturado = {}

        def handler(request: httpx.Request) -> httpx.Response:
            capturado["caminho"] = request.url.path
            capturado["params"] = dict(request.url.params)
            return httpx.Response(200, json={"resultado": [], "paginasRestantes": 0})

        with _client_falso(handler) as client:
            client.itens_de_ata_do_fornecedor("22015414000127", "2025-11-08", "2026-11-07")

        self.assertEqual(capturado["caminho"], "/modulo-arp/2_consultarARPItem")
        self.assertEqual(capturado["params"]["dataVigenciaInicialMin"], "2025-11-08")
        self.assertEqual(capturado["params"]["dataVigenciaInicialMax"], "2026-11-07")

    def test_outro_erro_continua_sendo_erro(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="falhou")

        with _client_falso(handler) as client, self.assertRaises(ComprasGovClientError):
            client.resultados_do_fornecedor("22015414000127", "2025-11-08", "2026-11-07")

    def test_periodo_maior_que_365_dias_vira_varias_consultas(self):
        periodos = []

        def handler(request: httpx.Request) -> httpx.Response:
            params = dict(request.url.params)
            periodos.append((params["dataResultadoPncpInicial"], params["dataResultadoPncpFinal"]))
            return httpx.Response(200, json={"resultado": [{"x": len(periodos)}], "paginasRestantes": 0})

        with _client_falso(handler) as client:
            registros = client.resultados_do_fornecedor("22015414000127", "2025-10-03", "2026-11-07")

        self.assertEqual(periodos, [("2025-10-03", "2026-10-02"), ("2026-10-03", "2026-11-07")])
        self.assertEqual(len(registros), 2)
