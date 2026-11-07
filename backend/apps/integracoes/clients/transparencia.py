"""Cliente da API de dados do Portal da Transparência (CGU).

Base: https://api.portaldatransparencia.gov.br/api-de-dados — exige a chave
pessoal no cabeçalho `chave-api-dados` (cadastro gratuito com gov.br). Cobre
a despesa da **União**: empenho, liquidação e pagamento de órgãos federais.
Estados e prefeituras têm portais próprios, sem padrão, e ficam de fora.

Usamos um endpoint só: `despesas/documentos-por-favorecido`, que lista os
documentos de despesa de um CNPJ num ano e numa fase (1 empenho, 2
liquidação, 3 pagamento). Páginas de 15 registros; acabou quando vem vazia.

Formato (conferido em 07/11/2026): `data` em "dd/mm/aaaa", `valor` em
"1.234,56" (estorno vem negativo, "- 2.140,82"), `documento` é o código
completo e único (UG + gestão + número), `numeroProcesso` é o processo
administrativo do órgão — às vezes vazio no pagamento, que então costuma
citá-lo na `observacao`.
"""

from __future__ import annotations

import datetime as dt
import time
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from config.settings.environment import env

# O Portal limita a ~90 requisições por minuto em horário comercial: uma
# pausa curta entre páginas fica bem abaixo disso.
INTERVALO_SEGUNDOS = 0.7
PAGINAS_MAX = 200

FASE_EMPENHO = 1
FASE_LIQUIDACAO = 2
FASE_PAGAMENTO = 3


class TransparenciaError(RuntimeError):
    pass


def valor_brasileiro(texto: Any) -> Decimal | None:
    """"43.945.314,38" → Decimal("43945314.38"); "- 2.140,82" → -2140.82."""

    if texto is None or texto == "":
        return None
    limpo = str(texto).replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return Decimal(limpo)
    except InvalidOperation:
        return None


def data_brasileira(texto: Any) -> dt.date | None:
    try:
        return dt.datetime.strptime(str(texto), "%d/%m/%Y").date()
    except (TypeError, ValueError):
        return None


class PortalTransparenciaClient:
    def __init__(
        self,
        chave: str | None = None,
        base_url: str | None = None,
        timeout: float = 60.0,
        intervalo: float = INTERVALO_SEGUNDOS,
    ) -> None:
        self.chave = env.portal_transparencia_chave if chave is None else chave
        self.intervalo = intervalo
        cabecalhos = {"accept": "application/json"}
        if self.chave:
            cabecalhos["chave-api-dados"] = self.chave
        self._client = httpx.Client(
            base_url=(base_url or env.portal_transparencia_base_url).rstrip("/"),
            headers=cabecalhos,
            timeout=timeout,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "PortalTransparenciaClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def _get(self, caminho: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            resp = self._client.get(caminho, params=params)
        except httpx.HTTPError as exc:
            raise TransparenciaError(f"Falha ao consultar o Portal da Transparência: {exc}") from exc
        if resp.status_code in (401, 403):
            raise TransparenciaError(
                "O Portal da Transparência recusou a chave (PORTAL_TRANSPARENCIA_CHAVE ausente ou inválida)."
            )
        if resp.status_code >= 400:
            raise TransparenciaError(
                f"Portal da Transparência respondeu {resp.status_code} em {caminho}: {resp.text[:300]}"
            )
        dados = resp.json()
        return dados if isinstance(dados, list) else []

    def documentos_do_favorecido(self, cnpj: str, fase: int, ano: int) -> list[dict[str, Any]]:
        """Todos os documentos de despesa do CNPJ (só dígitos) na fase e no ano."""

        documentos: list[dict[str, Any]] = []
        for pagina in range(1, PAGINAS_MAX + 1):
            if pagina > 1 and self.intervalo:
                time.sleep(self.intervalo)
            lote = self._get(
                "/despesas/documentos-por-favorecido",
                {"codigoPessoa": cnpj, "fase": fase, "ano": ano, "pagina": pagina},
            )
            if not lote:
                break
            documentos.extend(lote)
        return documentos
