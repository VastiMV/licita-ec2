"""O que a Sentinela captura no Compras.gov.br vira fato da Torre.

A extensão não interpreta nada: ela manda o **endereço** que a página do
Compras.gov.br chamou e a **resposta** que a página recebeu, como vieram.
Toda a leitura mora aqui, em Python, testável com as respostas reais
(gravadas em 07/11/2026 na sessão do Carlinhos).

| Endereço (capturado) | O que vira |
|---|---|
| `compras/participacoes` | a compra (criada se não estava no Licita) e a `ParticipacaoCompra` |
| `compras/{código}/participacao` | idem, de uma compra só |
| `compras/{código}/itens/em-selecao-fornecedores?filtro=2` | os itens **da empresa**, com a proposta dela (`ItemParticipado`) |
| `.../participacoes/{CNPJ}/itens/{n}/propostas` | a proposta da empresa num item |

**Captcha:** a lista de participações e a de itens são telas que pedem
captcha. A Sentinela **nunca** gera nem resolve captcha: ela só repassa o que
a página já recebeu quando o Carlinhos abriu a tela (ver docs/SENTINELA.md).

**Estar em "participações" não prova proposta** (a lista pode trazer compra
em que a empresa não lançou preço). Quem diz se há proposta é a lista de itens da
empresa: com item, há proposta; vazia na primeira página, não há.
"""

from __future__ import annotations

import datetime as dt
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

from django.db import transaction

from apps.empresas.models import Empresa
from apps.integracoes.clients.compras_gov import montar_link_compras_gov, montar_link_pncp
from apps.integracoes.plataformas import plataforma_padrao
from apps.licitacoes.models import (
    EventoOportunidadeSalva,
    Fonte,
    ItemParticipado,
    OportunidadeSalva,
    ParticipacaoCompra,
)
from apps.licitacoes.torre import MODALIDADE_COMPRAS_GOV

BRASILIA = ZoneInfo("America/Sao_Paulo")

_BASE = r"/comprasnet-fase-externa/v1/compras"
ROTAS = [
    (re.compile(_BASE + r"/participacoes/?$"), "participacoes"),
    (re.compile(_BASE + r"/(?P<codigo>\d{17})/participacao/?$"), "participacao"),
    (re.compile(_BASE + r"/(?P<codigo>\d{17})/itens/em-selecao-fornecedores/?$"), "itens"),
    (
        re.compile(
            _BASE
            + r"/(?P<codigo>\d{17})/em-selecao-fornecedores/participacoes/(?P<cnpj>\d{14})"
            r"/itens/(?P<item>[^/]+)/propostas/?$"
        ),
        "proposta_do_item",
    ),
]

SITUACOES_DA_COMPRA = {c.value for c in ParticipacaoCompra.Situacao}
SITUACOES_DA_PROPOSTA = {c.value for c in ItemParticipado.SituacaoProposta}


class CapturaInvalida(ValueError):
    """O que chegou não tem o formato esperado (a tela do Compras.gov mudou?)."""


def receber(url: str, dados) -> dict:
    """Lê uma captura. Devolve o tipo e um resumo do que mudou."""

    partes = urlsplit(url)
    for padrao, tipo in ROTAS:
        if achado := padrao.search(partes.path):
            params = {k: v[0] for k, v in parse_qs(partes.query).items()}
            with transaction.atomic():
                resumo = LEITORES[tipo](dados, params=params, **achado.groupdict())
            return {"tipo": tipo, **resumo}
    return {"tipo": "ignorado"}


# -- leitores ----------------------------------------------------------------


def _ler_participacoes(dados, params, **_) -> dict:
    if not isinstance(dados, list):
        raise CapturaInvalida("participações: era esperada uma lista")
    resumo = {"compras": 0, "criadas": 0}
    for registro in dados:
        compra = registro.get("compra") or {}
        salva, criada = _salva_da_compra(compra)
        if not salva:
            continue
        _gravar_participacao(salva, compra, registro)
        resumo["compras"] += 1
        resumo["criadas"] += int(criada)
    return resumo


def _ler_participacao(dados, params, codigo, **_) -> dict:
    if not isinstance(dados, dict):
        raise CapturaInvalida("participação: era esperado um objeto")
    if dados.get("isFornecedorParticipante") is False:
        return {"compras": 0, "criadas": 0}
    salva, criada = _salva_da_compra(dados, codigo=codigo)
    if not salva:
        return {"compras": 0, "criadas": 0}
    _gravar_participacao(salva, dados, dados)
    return {"compras": 1, "criadas": int(criada)}


def _ler_itens(dados, params, codigo, **_) -> dict:
    """Só a lista "meus itens" (`filtro=2`) diz o que é da empresa."""

    if params.get("filtro") != "2":
        return {"itens": 0, "motivo": "lista de todos os itens (filtro≠2) não diz quais são da empresa"}
    if not isinstance(dados, list):
        raise CapturaInvalida("itens: era esperada uma lista")
    salva = _salva_pelo_codigo(codigo)
    if not salva:
        return {"itens": 0, "motivo": "compra desconhecida: abra antes as participações"}

    cnpjs = _cnpjs_da_empresa()
    gravados = sum(_gravar_item(salva, item, cnpjs) for item in dados)
    primeira_pagina = params.get("pagina", "0") in ("0", "")
    if gravados or primeira_pagina:
        # Com item, há proposta. Primeira página vazia: participa sem proposta.
        _marcar_proposta(salva, bool(gravados))
    return {"itens": gravados}


def _ler_proposta_do_item(dados, params, codigo, cnpj, item, **_) -> dict:
    if cnpj not in _cnpjs_da_empresa():
        return {"itens": 0, "motivo": "proposta de outro CNPJ"}
    registros = dados if isinstance(dados, list) else [dados]
    salva = _salva_pelo_codigo(codigo)
    if not salva:
        return {"itens": 0, "motivo": "compra desconhecida: abra antes as participações"}
    gravados = sum(_gravar_item(salva, registro, {cnpj}) for registro in registros if isinstance(registro, dict))
    if gravados:
        _marcar_proposta(salva, True)
    return {"itens": gravados}


LEITORES = {
    "participacoes": _ler_participacoes,
    "participacao": _ler_participacao,
    "itens": _ler_itens,
    "proposta_do_item": _ler_proposta_do_item,
}


# -- a compra ------------------------------------------------------------------


def codigo_da_compra(compra: dict) -> str | None:
    """UASG (6) + modalidade (2) + número (5) + ano (4): o `compra=` dos links."""

    try:
        return (
            f"{int(compra['numeroUasg']):06d}{int(compra['modalidade']):02d}"
            f"{int(compra['numero']):05d}{int(compra['ano']):04d}"
        )
    except (KeyError, TypeError, ValueError):
        return None


def _chave_pncp(chave: str | None) -> tuple[str, str, str] | None:
    """"0894261000011610000912026" → ("08942610000116", "2026", "91")."""

    if not chave or not re.fullmatch(r"\d{25}", chave):
        return None
    return chave[:14], chave[21:25], str(int(chave[15:21]))


def _salva_pelo_codigo(codigo: str) -> OportunidadeSalva | None:
    return OportunidadeSalva.objects.ativas().filter(link_plataforma__contains=f"compra={codigo}").first()


def _salva_da_compra(compra: dict, codigo: str | None = None) -> tuple[OportunidadeSalva | None, bool]:
    """A salva da compra; criada se o Licita ainda não a conhecia (decisão da
    operação, 08/11/2026: o que ele disputa no Compras.gov tem que aparecer)."""

    codigo = codigo or codigo_da_compra(compra)
    chave = _chave_pncp(compra.get("chaveCompraPncp"))
    ativas = OportunidadeSalva.objects.ativas()
    salva = None
    if chave:
        cnpj, ano, sequencial = chave
        salva = ativas.filter(
            cnpj_orgao=cnpj, ano_compra=ano, sequencial_compra__in={sequencial, sequencial.zfill(6)}
        ).first()
    if not salva and codigo:
        salva = _salva_pelo_codigo(codigo)
    if salva:
        if codigo and f"compra={codigo}" not in (salva.link_plataforma or ""):
            # Salva de outra origem sem o link do Compras.gov: é o que liga as
            # próximas capturas (itens, propostas) a ela.
            salva.link_plataforma = montar_link_compras_gov({"id_compra": codigo}) or salva.link_plataforma
            salva.save(update_fields=["link_plataforma"])
        return salva, False
    if not (chave and codigo):
        return None, False

    cnpj, ano, sequencial = chave
    modalidade = MODALIDADE_COMPRAS_GOV.get(f"{int(compra.get('modalidade') or 0):02d}", "")
    salva = OportunidadeSalva.objects.create(
        cnpj_orgao=cnpj,
        ano_compra=ano,
        sequencial_compra=sequencial,
        objeto=compra.get("objetoCompra") or compra.get("objeto") or "",
        orgao_nome=compra.get("nomeUasg") or compra.get("nomeOrgao") or "",
        uasg=str(compra.get("numeroUasg") or ""),
        uf=compra.get("ufUasg") or "",
        modalidade=f"{modalidade} - Eletrônico" if modalidade else "",
        data_encerramento_proposta=_data(compra.get("dataHoraFimPropostas")),
        plataforma_id=plataforma_padrao().id,
        plataforma_nome=plataforma_padrao().nome,
        link_plataforma=montar_link_compras_gov({"id_compra": codigo}) or "",
        link_pncp=montar_link_pncp({"cnpj_orgao": cnpj, "ano_compra": ano, "sequencial_compra": sequencial})
        or "",
    )
    salva.registrar(
        EventoOportunidadeSalva.Tipo.SALVA,
        autor=None,
        descricao="Trazida pela Sentinela: a empresa está participando desta compra no Compras.gov.br.",
    )
    return salva, True


def _gravar_participacao(salva: OportunidadeSalva, compra: dict, registro: dict) -> None:
    valores = {"fonte": Fonte.SENTINELA}
    if fase := compra.get("faseCompraFaseExterna"):
        valores["fase_compra"] = str(fase)
    if (situacao := compra.get("situacaoCompraFaseExterna")) in SITUACOES_DA_COMPRA:
        valores["situacao_compra"] = situacao
    if "possuiDiligenciaEmAndamento" in registro:
        valores["diligencia_em_andamento"] = bool(registro["possuiDiligenciaEmAndamento"])
    if "possuiConvRemanescentesEmAndamento" in registro:
        valores["convocacao_em_andamento"] = bool(registro["possuiConvRemanescentesEmAndamento"])
    if abre := _data_hora(compra.get("dataHoraPrevisaoAbertura")):
        valores["sessao_abre_em"] = abre
    ParticipacaoCompra.objects.update_or_create(oportunidade=salva, defaults=valores)

    if not salva.data_encerramento_proposta and (fim := _data(compra.get("dataHoraFimPropostas"))):
        salva.data_encerramento_proposta = fim
        salva.save(update_fields=["data_encerramento_proposta"])


def _marcar_proposta(salva: OportunidadeSalva, tem: bool) -> None:
    ParticipacaoCompra.objects.update_or_create(
        oportunidade=salva, defaults={"proposta_cadastrada": tem, "fonte": Fonte.SENTINELA}
    )


# -- o item --------------------------------------------------------------------


def _cnpjs_da_empresa() -> set[str]:
    return set(Empresa.objects.filter(ativa=True).values_list("cnpj", flat=True))


def _gravar_item(salva: OportunidadeSalva, item: dict, cnpjs: set[str]) -> int:
    """Grava um item da empresa. Devolve 1 se gravou, 0 se não era dela."""

    proposta = item.get("propostaItem") or {}
    participante = (proposta.get("participante") or {}).get("identificacao")
    if participante and participante not in cnpjs:
        return 0
    numero = str(item.get("identificador") or item.get("numero") or "").strip()
    if not numero:
        return 0

    valores = proposta.get("valores") or {}
    situacao = str(proposta.get("situacao") or "")
    anexo = str(proposta.get("situacaoUltimaSolicitacaoAnexos") or "")
    ItemParticipado.objects.update_or_create(
        oportunidade=salva,
        numero_item=numero,
        defaults={
            "descricao": item.get("descricao") or "",
            "quantidade": _decimal(proposta.get("quantidadeOfertada") or item.get("quantidadeSolicitada")),
            "marca": (proposta.get("marcaFabricante") or "")[:120],
            "modelo": (proposta.get("modeloVersao") or "")[:120],
            "classificacao": proposta.get("classificacao") or None,
            "situacao_proposta": situacao if situacao in SITUACOES_DA_PROPOSTA else "",
            "fase_item": str(item.get("fase") or "")[:4],
            "anexo_solicitado": anexo if anexo in {"S", "P", "E"} else "",
            "negociacao": str(proposta.get("situacaoUltimaNegociacao") or "")[:1],
            "negociacao_texto": proposta.get("justificativaUltimaNegociacao") or "",
            "valor_proposta_inicial": _valor(valores.get("valorPropostaInicial")),
            "valor_lance_final": _valor(valores.get("valorPropostaInicialOuLances")),
            "fonte": Fonte.SENTINELA,
        },
    )
    return 1


# -- conversões ------------------------------------------------------------------


def _decimal(valor) -> Decimal | None:
    if valor is None or valor == "":
        return None
    try:
        return Decimal(str(valor))
    except (InvalidOperation, ValueError):
        return None


def _valor(bloco) -> Decimal | None:
    """`{"valorInformado": 12199.0, "valorCalculado": {"valorUnitario": …}}` → unitário."""

    if not isinstance(bloco, dict):
        return None
    calculado = bloco.get("valorCalculado") or {}
    return _decimal(calculado.get("valorUnitario", bloco.get("valorInformado")))


def _data(texto) -> dt.date | None:
    if not texto:
        return None
    try:
        return dt.date.fromisoformat(str(texto)[:10])
    except ValueError:
        return None


def _data_hora(texto) -> dt.datetime | None:
    if not texto:
        return None
    try:
        momento = dt.datetime.fromisoformat(str(texto))
    except ValueError:
        return None
    return momento if momento.tzinfo else momento.replace(tzinfo=BRASILIA)
