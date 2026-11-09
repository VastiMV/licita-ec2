"""Cliente para a API de Dados Abertos do compras.gov.br.

Base: https://dadosabertos.compras.gov.br — API pública (sem autenticação),
organizada em módulos. Usamos o módulo de contratações da Lei 14.133 (a lei de
licitações vigente), que é onde estão as oportunidades atuais:

- `/modulo-contratacoes/1_consultarContratacoes_PNCP_14133` — lista contratações
  (a "licitação"). Exige faixa de data de publicação e código de modalidade.
- `/modulo-contratacoes/2.1_consultarItensContratacoes_PNCP_14133_Id` — lista os
  itens de uma contratação específica, incluindo `descricaodetalhada`, que é a
  descrição do item tal como consta no edital.

Toda resposta vem no envelope
`{"resultado": [...], "totalRegistros": N, "totalPaginas": N, "paginasRestantes": N}`.

Portado do protótipo (branch `claude/tenta-de-novo-xu2sxb`, `app/clients/compras_gov.py`),
já validado contra a API real — ver docs/DOMINIO.md. Os nomes de campo vêm da
especificação OpenAPI real da API (`api-spec.json` no branch do protótipo).
"""

from __future__ import annotations

import datetime as dt
import json
import unicodedata
from typing import Any

import httpx

from config.settings.environment import env

# A API rejeita paginação fora desta faixa com HTTP 400.
TAMANHO_PAGINA_MIN = 10
TAMANHO_PAGINA_MAX = 500

# Intervalo máximo de datas que os módulos aceitam numa consulta.
PERIODO_MAX_DIAS = 365


def _pagina_valida(tamanho: int) -> int:
    return max(TAMANHO_PAGINA_MIN, min(TAMANHO_PAGINA_MAX, tamanho))


def normalizar(texto: str) -> str:
    """Caixa alta e sem acento — como o catálogo guarda os nomes."""

    return sem_acento(texto).upper().strip()


def sem_acento(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c))


# Tabela oficial de modalidades da Lei 14.133, como o PNCP as codifica (usada
# nos campos de resposta como `modalidade_licitacao_id` da busca textual do
# PNCP — ver clients/pncp.py). NÃO é o que o filtro `codigoModalidade` deste
# client (compras.gov.br) espera — ver MODALIDADES_CONTRATACOES abaixo.
MODALIDADES = {
    "1": "Leilão - Eletrônico",
    "2": "Diálogo Competitivo",
    "3": "Concurso",
    "4": "Concorrência - Eletrônica",
    "5": "Concorrência - Presencial",
    "6": "Pregão - Eletrônico",
    "7": "Pregão - Presencial",
    "8": "Dispensa de Licitação",
    "9": "Inexigibilidade",
    "10": "Manifestação de Interesse",
    "11": "Pré-qualificação",
    "12": "Credenciamento",
    "13": "Leilão - Presencial",
}

# Códigos que o filtro `codigoModalidade` de
# `1_consultarContratacoes_PNCP_14133` (e os demais endpoints deste módulo)
# realmente espera — confirmado empiricamente contra a API real em
# 26/08/2026 (ver docs/DOMINIO.md): varridos os 13 códigos de MODALIDADES
# contra um ano inteiro de dados, só estes quatro devolveram algo; os outros
# nove aceitam a requisição (sem erro) mas nunca trazem registro — não é a
# mesma numeração do PNCP (ali "6" é Pregão Eletrônico; aqui é Dispensa).
# Usar SEMPRE esta tabela para `codigo_modalidade` nas chamadas a este
# client — nunca a MODALIDADES acima.
MODALIDADES_CONTRATACOES = {
    "3": "Concorrência - Eletrônica",
    "5": "Pregão - Eletrônico",
    "6": "Dispensa",
    "7": "Inexigibilidade",
}

# Tradução do código acima (o que o dropdown do frontend manda) para o código
# que a busca textual do PNCP espera no parâmetro `modalidades` de
# `/api/search/` (ver apps/integracoes/clients/pncp.py) — que usa a tabela
# MODALIDADES, não esta. Confirmado contra a API real em 26/08/2026 (ver
# docs/DOMINIO.md): mandar o código deste módulo direto pro PNCP filtrava
# silenciosamente pela modalidade errada (ex.: "5" = Pregão Eletrônico aqui,
# mas Concorrência - Presencial lá) — sem erro, só resultado errado.
MODALIDADE_CONTRATACOES_PARA_PNCP: dict[str, str] = {
    "3": "4",  # Concorrência - Eletrônica
    "5": "6",  # Pregão - Eletrônico
    "6": "8",  # Dispensa (lá é "Dispensa de Licitação")
    "7": "9",  # Inexigibilidade
}

# Caminho inverso: um edital que veio da busca textual do PNCP traz o código
# de modalidade na tabela do PNCP, mas o `idCompra` do Comprasnet embute o
# código da tabela deste módulo (ver `_montar_id_compra` em clients/pncp.py).
MODALIDADE_PNCP_PARA_CONTRATACOES: dict[str, str] = {
    pncp: contratacoes for contratacoes, pncp in MODALIDADE_CONTRATACOES_PARA_PNCP.items()
}


class ComprasGovClientError(RuntimeError):
    pass


class ComprasGovClient:
    def __init__(self, base_url: str | None = None, timeout: float = 60.0) -> None:
        self.base_url = (base_url or env.compras_gov_base_url).rstrip("/")
        self._client = httpx.Client(base_url=self.base_url, timeout=timeout, follow_redirects=True)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "ComprasGovClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def _get(self, caminho: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            resp = self._client.get(caminho, params=params)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detalhe = exc.response.text[:300]
            raise ComprasGovClientError(
                f"compras.gov.br respondeu {exc.response.status_code} em {caminho}: {detalhe}"
            ) from exc
        except httpx.HTTPError as exc:
            raise ComprasGovClientError(f"Falha ao consultar compras.gov.br: {exc}") from exc

        try:
            return resp.json()
        except ValueError as exc:
            raise ComprasGovClientError(f"Resposta inválida (não-JSON) em {caminho}") from exc

    def buscar_contratacoes(
        self,
        *,
        data_publicacao_inicial: str,  # AAAA-MM-DD
        data_publicacao_final: str,  # AAAA-MM-DD
        codigo_modalidade: str,
        uf: str | None = None,
        codigo_unidade: str | None = None,
        pagina: int = 1,
        tamanho_pagina: int = 50,
    ) -> tuple[list[dict[str, Any]], int]:
        """Busca contratações (licitações). Retorna (lista normalizada, total de páginas)."""

        params: dict[str, Any] = {
            "dataPublicacaoPncpInicial": data_publicacao_inicial,
            "dataPublicacaoPncpFinal": data_publicacao_final,
            "codigoModalidade": codigo_modalidade,
            "pagina": pagina,
            "tamanhoPagina": _pagina_valida(tamanho_pagina),
        }
        if uf:
            params["unidadeOrgaoUfSigla"] = uf.upper()
        if codigo_unidade:
            params["unidadeOrgaoCodigoUnidade"] = codigo_unidade

        payload = self._get("/modulo-contratacoes/1_consultarContratacoes_PNCP_14133", params)
        resultado = payload.get("resultado") or []
        total_paginas = payload.get("totalPaginas") or 1
        return [_normalizar_contratacao(c) for c in resultado], total_paginas

    def detalhar_contratacao(self, id_compra: str) -> dict[str, Any] | None:
        """Busca uma contratação específica pelo idCompra."""

        payload = self._get(
            "/modulo-contratacoes/1.1_consultarContratacoes_PNCP_14133_Id",
            {"tipo": "idCompra", "codigo": id_compra},
        )
        resultado = payload.get("resultado") or []
        return _normalizar_contratacao(resultado[0]) if resultado else None

    def _paginar(self, caminho: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Todas as páginas de uma consulta. O módulo responde **404** quando
        não há nada no filtro (e às vezes em instabilidade, ver o Comunicado
        nº 18/26): para quem lê, é lista vazia, não erro."""

        registros: list[dict[str, Any]] = []
        pagina = 1
        while True:
            try:
                payload = self._get(caminho, {**params, "pagina": pagina, "tamanhoPagina": TAMANHO_PAGINA_MAX})
            except ComprasGovClientError as exc:
                if " 404 " in str(exc):
                    return registros
                raise
            registros.extend(payload.get("resultado") or [])
            if not payload.get("paginasRestantes"):
                return registros
            pagina += 1

    def _paginar_por_periodo(
        self,
        caminho: str,
        params: dict[str, Any],
        nomes: tuple[str, str],
        inicio: str,
        fim: str,
    ) -> list[dict[str, Any]]:
        """Como `_paginar`, mas quebrando o período em pedaços de até
        `PERIODO_MAX_DIAS`: a API responde 400 ("Período inicial e final maior
        que 365 dias") a um intervalo maior."""

        de = dt.date.fromisoformat(inicio)
        ate = dt.date.fromisoformat(fim)
        registros: list[dict[str, Any]] = []
        while de <= ate:
            fim_do_pedaco = min(ate, de + dt.timedelta(days=PERIODO_MAX_DIAS - 1))
            registros.extend(
                self._paginar(caminho, {**params, nomes[0]: de.isoformat(), nomes[1]: fim_do_pedaco.isoformat()})
            )
            de = fim_do_pedaco + dt.timedelta(days=1)
        return registros

    def resultados_do_fornecedor(self, ni_fornecedor: str, inicio: str, fim: str) -> list[dict[str, Any]]:
        """Itens homologados para o fornecedor (CNPJ só dígitos) entre `inicio`
        e `fim` (AAAA-MM-DD, data do resultado no PNCP). Cada registro traz
        `idContratacaoPNCP` ("cnpj-1-sequencial/ano"), a chave da compra."""

        return self._paginar_por_periodo(
            "/modulo-contratacoes/3_consultarResultadoItensContratacoes_PNCP_14133",
            {"niFornecedor": ni_fornecedor},
            ("dataResultadoPncpInicial", "dataResultadoPncpFinal"),
            inicio,
            fim,
        )

    def itens_de_ata_do_fornecedor(self, ni_fornecedor: str, inicio: str, fim: str) -> list[dict[str, Any]]:
        """Itens de atas de registro de preços do fornecedor com vigência
        iniciada entre `inicio` e `fim`. Traz vigência, quantidade homologada
        e **quantidade já empenhada** — o saldo da ata."""

        return self._paginar_por_periodo(
            "/modulo-arp/2_consultarARPItem",
            {"niFornecedor": ni_fornecedor},
            ("dataVigenciaInicialMin", "dataVigenciaInicialMax"),
            inicio,
            fim,
        )

    def itens_de_ata_da_unidade(self, codigo_unidade: str, inicio: str, fim: str) -> list[dict[str, Any]]:
        """Itens de atas de registro de preços de uma unidade (UASG) com
        vigência iniciada entre `inicio` e `fim`: item, fornecedor e data de
        assinatura. É como a vigia sabe que a ata foi assinada com outra
        empresa (filtro testado ao vivo em 09/11/2026)."""

        return self._paginar_por_periodo(
            "/modulo-arp/2_consultarARPItem",
            {"codigoUnidadeGerenciadora": codigo_unidade},
            ("dataVigenciaInicialMin", "dataVigenciaInicialMax"),
            inicio,
            fim,
        )

    def listar_itens(self, id_compra: str) -> list[dict[str, Any]]:
        """Lista os itens de uma contratação — o que efetivamente é precificado."""

        payload = self._get(
            "/modulo-contratacoes/2.1_consultarItensContratacoes_PNCP_14133_Id",
            {"tipo": "idCompra", "codigo": id_compra},
        )
        return [_normalizar_item(i) for i in (payload.get("resultado") or [])]

    def listar_pdms(
        self, *, pagina: int = 1, tamanho_pagina: int = TAMANHO_PAGINA_MAX
    ) -> tuple[list[dict[str, Any]], int]:
        """Uma página do catálogo de PDMs. Retorna (lista, total de páginas)."""

        payload = self._get(
            "/modulo-material/3_consultarPdmMaterial",
            {"pagina": pagina, "tamanhoPagina": _pagina_valida(tamanho_pagina)},
        )
        pdms = [
            {
                "codigo_pdm": p.get("codigoPdm"),
                "nome_pdm": p.get("nomePdm"),
                "codigo_classe": p.get("codigoClasse"),
                "nome_classe": p.get("nomeClasse"),
                "codigo_grupo": p.get("codigoGrupo"),
                "nome_grupo": p.get("nomeGrupo"),
            }
            for p in (payload.get("resultado") or [])
            if p.get("codigoPdm") is not None
        ]
        return pdms, payload.get("totalPaginas") or 1

    def buscar_itens_por_pdm(
        self,
        *,
        codigo_pdm: int,
        data_inicial: str,
        data_final: str,
        tamanho_pagina: int = 100,
    ) -> list[dict[str, Any]]:
        """Lista itens de contratações que compram materiais de um PDM."""

        return self._buscar_itens_contratacoes(
            {"codigoPdm": codigo_pdm},
            data_inicial=data_inicial,
            data_final=data_final,
            tamanho_pagina=tamanho_pagina,
        )

    def buscar_itens_por_catalogo(
        self,
        *,
        cod_item_catalogo: int,
        data_inicial: str,
        data_final: str,
        tamanho_pagina: int = 100,
    ) -> list[dict[str, Any]]:
        """Lista itens de contratações que compram um código de catálogo específico."""

        return self._buscar_itens_contratacoes(
            {"codItemCatalogo": cod_item_catalogo},
            data_inicial=data_inicial,
            data_final=data_final,
            tamanho_pagina=tamanho_pagina,
        )

    def _buscar_itens_contratacoes(
        self,
        filtro: dict[str, Any],
        *,
        data_inicial: str,
        data_final: str,
        tamanho_pagina: int,
    ) -> list[dict[str, Any]]:
        payload = self._get(
            "/modulo-contratacoes/2_consultarItensContratacoes_PNCP_14133",
            {
                **filtro,
                "dataInclusaoPncpInicial": data_inicial,
                "dataInclusaoPncpFinal": data_final,
                "tamanhoPagina": _pagina_valida(tamanho_pagina),
            },
        )
        itens = []
        for i in payload.get("resultado") or []:
            item = _normalizar_item(i)
            item["id_compra"] = i.get("idCompra")
            itens.append(item)
        return itens


def _normalizar_contratacao(c: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_compra": c.get("idCompra"),
        "numero_controle_pncp": c.get("numeroControlePNCP"),
        "uasg": c.get("unidadeOrgaoCodigoUnidade"),
        "orgao_nome": c.get("unidadeOrgaoNomeUnidade") or c.get("orgaoEntidadeRazaoSocial"),
        "cnpj_orgao": c.get("orgaoEntidadeCnpj"),
        "uf": c.get("unidadeOrgaoUfSigla"),
        "municipio": c.get("unidadeOrgaoMunicipioNome"),
        "numero_compra": c.get("numeroCompra"),
        "ano_compra": c.get("anoCompraPncp"),
        "sequencial_compra": c.get("sequencialCompraPncp"),
        "modalidade": c.get("modalidadeNome"),
        "codigo_modalidade": c.get("codigoModalidade"),
        "objeto": c.get("objetoCompra"),
        "processo": c.get("processo"),
        "situacao": c.get("situacaoCompraNomePncp"),
        "srp": c.get("srp"),
        "valor_total_estimado": c.get("valorTotalEstimado"),
        "data_publicacao": _so_data(c.get("dataPublicacaoPncp")),
        "data_abertura_proposta": _so_data(c.get("dataAberturaPropostaPncp")),
        "data_encerramento_proposta": _so_data(c.get("dataEncerramentoPropostaPncp")),
        "raw_json": json.dumps(c, ensure_ascii=False),
    }


def _normalizar_item(i: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_compra_item": i.get("idCompraItem"),
        "numero_item": i.get("numeroItemCompra") or i.get("numeroItemPncp"),
        "descricao_resumida": i.get("descricaoResumida"),
        # A descrição detalhada é o texto do item como consta no edital.
        "descricao_detalhada": i.get("descricaodetalhada"),
        "material_ou_servico": i.get("materialOuServicoNome"),
        "quantidade": i.get("quantidade"),
        "unidade_medida": i.get("unidadeMedida"),
        "valor_unitario_estimado": i.get("valorUnitarioEstimado"),
        "valor_total": i.get("valorTotal"),
        "situacao": i.get("situacaoCompraItemNome"),
        "criterio_julgamento": i.get("criterioJulgamentoNome"),
        "tipo_beneficio": i.get("tipoBeneficioNome"),
        "tem_resultado": i.get("temResultado"),
    }


def _so_data(valor: Any) -> str | None:
    """A API devolve 'AAAA-MM-DD HH:MM:SS'; para exibição basta a data."""

    if not valor or not isinstance(valor, str):
        return None
    return valor.split(" ")[0].split("T")[0]


def montar_link_compras_gov(contratacao: dict[str, Any]) -> str | None:
    """Link para a tela de acompanhamento da compra no compras.gov.br (Comprasnet),
    onde dá para ver e precificar os itens.

    O `idCompra` da API é o código da compra no formato usado pelo Comprasnet
    (UASG + modalidade + número + ano, 17 dígitos — conferido contra o
    `linkSistemaOrigem` que o próprio PNCP devolve para compras do
    Comprasnet, ver docs/DOMINIO.md, achado de 28/08/2026), que é o parâmetro
    esperado por essa tela. Sem `id_compra` não há link — devolver a URL sem
    o parâmetro só renderia um botão que dá 404.
    """

    id_compra = contratacao.get("id_compra")
    if not id_compra:
        return None
    return (
        "https://cnetmobile.estaleiro.serpro.gov.br/comprasnet-web/public/compras/"
        f"acompanhamento-compra?compra={id_compra}"
    )


def montar_link_pncp(contratacao: dict[str, Any]) -> str | None:
    """Link para o edital no PNCP — útil como alternativa, e é onde costuma estar
    o PDF do edital completo."""

    cnpj = contratacao.get("cnpj_orgao")
    ano = contratacao.get("ano_compra")
    seq = contratacao.get("sequencial_compra")
    if not (cnpj and ano and seq):
        return None
    return f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{seq}"
