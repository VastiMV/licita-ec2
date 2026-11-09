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
| `compras/{código}/itens/aguardando-abertura-sessao-publica` (e `/{grupo}/itens-grupo`) | antes da sessão: os itens em que a empresa lançou preço |
| `compras/{código}/itens/{n}/fase-recursal-fornecedor/{sessão}` | recurso no item: quem, prazo de contrarrazões, decisão |
| `compras/{código}/itens/{n}/participacoes/{CNPJ}/diligencias` | diligências da empresa no item |

**Descartada não volta** (lixeira, 08/11/2026): a Sentinela continua
atualizando os fatos dela em silêncio, mas ela fica em Descartadas — **exceto
convocação** (anexo pedido ou chamada de remanescente): aí volta para a Torre
(`lixeira.voltar_por_convocacao`).
| `compras/{código}/em-selecao-fornecedores/itens/{n}/propostas` | as propostas de **todos** os participantes de um item da empresa (`PropostaDoItem`): quem está na frente, quem ganhou, marca, valor |

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
from django.utils import timezone

from apps.empresas.models import Empresa
from apps.integracoes.clients.compras_gov import montar_link_compras_gov, montar_link_pncp
from apps.integracoes.plataformas import plataforma_padrao
from apps.licitacoes.models import (
    EventoOportunidadeSalva,
    Fonte,
    ItemParticipado,
    OportunidadeSalva,
    ParticipacaoCompra,
    PropostaDoItem,
)
from apps.licitacoes.torre import MODALIDADE_COMPRAS_GOV, proposta_vencedora

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
    (
        re.compile(_BASE + r"/(?P<codigo>\d{17})/itens/aguardando-abertura-sessao-publica(?:/[^/]+/itens-grupo)?/?$"),
        "itens_antes_da_sessao",
    ),
    (
        re.compile(_BASE + r"/(?P<codigo>\d{17})/itens/(?P<item>[^/]+)/fase-recursal-fornecedor/(?P<sessao>\d+)/?$"),
        "fase_recursal",
    ),
    (
        re.compile(
            _BASE + r"/(?P<codigo>\d{17})/itens/(?P<item>[^/]+)/participacoes/(?P<cnpj>\d{14})/diligencias/?$"
        ),
        "diligencias",
    ),
    (
        re.compile(_BASE + r"/(?P<codigo>\d{17})/em-selecao-fornecedores/itens/(?P<item>[^/]+)/propostas/?$"),
        "propostas_do_item",
    ),
    (re.compile(r"/comprasnet-oportunidade/v1/compras/favoritas/dentre-opcoes/?$"), "favoritas"),
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
        _talvez_voltar(salva)
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
    """A lista de itens da compra, nos dois filtros da tela:

    - **"Itens em que estou participando"** (`filtro=2`): só os itens da
      empresa. Primeira página vazia = participa sem proposta.
    - **"Todos os itens"** (`filtro=1`, o padrão ao abrir a compra): traz a
      proposta da empresa **dentro** de cada item em que ela lançou preço
      (HARs de 08/11/2026: 61 com os itens 11, 12, 22, 24–27; 56 com 6 e 9;
      Cubatão com o 2). Só esses entram. Uma página sem proposta não prova
      nada — a lista vem de 10 em 10.
    """

    if not isinstance(dados, list):
        raise CapturaInvalida("itens: era esperada uma lista")
    salva = _salva_pelo_codigo(codigo)
    if not salva:
        return {"itens": 0, "motivo": "compra desconhecida: abra antes as participações"}

    cnpjs = _cnpjs_da_empresa()
    so_da_empresa = params.get("filtro") == "2"
    if so_da_empresa:
        gravados = sum(_gravar_item(salva, item, cnpjs) for item in dados)
    else:
        com_proposta = [
            item
            for item in dados
            if isinstance(item, dict)
            and ((item.get("propostaItem") or {}).get("participante") or {}).get("identificacao") in cnpjs
        ]
        gravados = sum(_gravar_item(salva, item, cnpjs) for item in com_proposta)
    primeira_pagina = params.get("pagina", "0") in ("0", "")
    if gravados or (so_da_empresa and primeira_pagina):
        # Com item, há proposta. "Meus itens" vazio na primeira página: sem proposta.
        _marcar_proposta(salva, bool(gravados))
    _talvez_voltar(salva)
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
    _talvez_voltar(salva)
    return {"itens": gravados}


def _ler_itens_antes_da_sessao(dados, params, codigo, **_) -> dict:
    """Antes da sessão, a lista de itens traz a proposta dentro do item em
    que a empresa lançou preço (142/2026: "Malinois", R$ 56.000,00) e nada nos
    outros (387/2026). Itens de grupo vêm noutra lista (`itens-grupo`), por
    isso uma página sem proposta **não** prova que não há proposta."""

    if not isinstance(dados, list):
        raise CapturaInvalida("itens antes da sessão: era esperada uma lista")
    salva = _salva_pelo_codigo(codigo)
    if not salva:
        return {"itens": 0, "motivo": "compra desconhecida: abra antes as participações"}
    cnpjs = _cnpjs_da_empresa()
    com_proposta = [item for item in dados if isinstance(item, dict) and item.get("propostaItem")]
    gravados = sum(_gravar_item(salva, item, cnpjs) for item in com_proposta)
    if gravados:
        _marcar_proposta(salva, True)
    return {"itens": gravados}


def _ler_fase_recursal(dados, params, codigo, item, sessao, **_) -> dict:
    """Quem entrou com recurso no item, até quando dá para responder
    (contrarrazões) e o que foi decidido. Caso real: 56/2026, item 22."""

    if not isinstance(dados, dict):
        raise CapturaInvalida("fase recursal: era esperado um objeto")
    salva = _salva_pelo_codigo(codigo)
    registro = salva and salva.itens_participados.filter(numero_item=str(item)).first()
    if not registro:
        return {"itens": 0, "motivo": "item desconhecido"}
    recursos = [
        {
            "cnpj": p.get("identificacaoParticipante") or "",
            "nome": p.get("nomeParticipante") or "",
            "em": p.get("dataHoraCadastro") or "",
        }
        for p in (dados.get("participacoes") or [])
        if isinstance(p, dict) and p.get("situacaoCadastroRecurso") == "C"
    ]
    prazos = dados.get("prazos") or {}
    revisao = (dados.get("revisaoDecisao") or {}).get("situacao") or ""
    decisao = (dados.get("decisao") or {}).get("situacao") or ""
    registro.recursos = recursos
    registro.prazo_contrarrazao = _data_hora(prazos.get("dataHoraLimiteContrarrazao"))
    registro.decisao_recurso = (revisao or decisao)[:1]
    registro.sessao_julgamento = int(sessao)
    registro.save(update_fields=["recursos", "prazo_contrarrazao", "decisao_recurso", "sessao_julgamento", "atualizado_em"])
    return {"itens": 1, "recursos": len(recursos)}


def _ler_diligencias(dados, params, codigo, item, cnpj, **_) -> dict:
    if cnpj not in _cnpjs_da_empresa():
        return {"itens": 0, "motivo": "diligência de outro CNPJ"}
    if not isinstance(dados, list):
        raise CapturaInvalida("diligências: era esperada uma lista")
    salva = _salva_pelo_codigo(codigo)
    registro = salva and salva.itens_participados.filter(numero_item=str(item)).first()
    if not registro:
        return {"itens": 0, "motivo": "item desconhecido"}
    # O formato de uma diligência ainda não foi visto (só listas vazias):
    # conta as que não vierem marcadas como encerradas.
    abertas = [d for d in dados if not (isinstance(d, dict) and str(d.get("situacao", "")).upper() in {"E", "F", "ENCERRADA", "FINALIZADA"})]
    registro.diligencias_abertas = min(len(abertas), 32767)
    registro.save(update_fields=["diligencias_abertas", "atualizado_em"])
    return {"itens": 1, "diligencias": len(abertas)}


def _ler_propostas_do_item(dados, params, codigo, item, **_) -> dict:
    """As propostas de todos os participantes de um item (HARs de 08/11/2026:
    59/2026 item 1, 4 propostas; Cubatão 55/2026 item 2, 31 propostas — a
    lista vem inteira numa resposta só, ordenada por valor).

    Só vale para item em que a empresa participa: os outros não interessam
    (e o Licita nem sabe deles). A linha da empresa também atualiza o
    `ItemParticipado` (posição, situação, valores)."""

    registros = dados if isinstance(dados, list) else [dados]
    registro = next((r for r in registros if isinstance(r, dict)), None)
    if registro is None:
        raise CapturaInvalida("propostas do item: era esperado um item")
    salva = _salva_pelo_codigo(codigo)
    if not salva:
        return {"propostas": 0, "motivo": "compra desconhecida: abra antes as participações"}
    numero = str(registro.get("identificador") or registro.get("numero") or item).strip()
    participado = ItemParticipado.objects.filter(oportunidade=salva, numero_item=numero).first()
    if not participado:
        return {"propostas": 0, "motivo": "item em que a empresa não participa"}

    cnpjs = _cnpjs_da_empresa()
    propostas = [p for p in registro.get("propostasItem") or [] if isinstance(p, dict)]
    novas = []
    for proposta in propostas:
        participante = proposta.get("participante") or {}
        valores = proposta.get("valores") or {}
        cnpj = str(participante.get("identificacao") or "")[:14]
        novas.append(
            PropostaDoItem(
                item=participado,
                classificacao=proposta.get("classificacao") or None,
                cnpj=cnpj,
                nome=(participante.get("nome") or "")[:255],
                uf=((participante.get("endereco") or {}).get("uf") or "")[:2],
                marca=(proposta.get("marcaFabricante") or "").strip()[:255],
                modelo=(proposta.get("modeloVersao") or "").strip()[:255],
                valor_inicial=_valor(valores.get("valorPropostaInicial")),
                valor_final=_valor(valores.get("valorPropostaInicialOuLances")),
                situacao=str(proposta.get("situacao") or "")[:2],
                da_empresa=cnpj in cnpjs,
            )
        )
    participado.propostas.all().delete()
    PropostaDoItem.objects.bulk_create(novas)

    da_empresa = next((p for p in propostas if ((p.get("participante") or {}).get("identificacao")) in cnpjs), None)
    if da_empresa:
        _gravar_item(salva, {**registro, "propostaItem": da_empresa}, cnpjs)
        participado.refresh_from_db()
    if registro.get("homologado") is True:
        vencedora = proposta_vencedora(novas)
        if vencedora is not None:
            participado.vencedor_e_a_empresa = vencedora.da_empresa
    participado.propostas_lidas_em = timezone.now()
    participado.save(update_fields=["vencedor_e_a_empresa", "propostas_lidas_em"])
    return {"propostas": len(novas)}


def _ler_favoritas(dados, params, **_) -> dict:
    """"Destas compras, quais estão nos favoritos?" — a resposta é a lista das
    que estão (HAR de 08/11/2026: `["98637105000552026"]`). A que foi
    perguntada e não voltou saiu dos favoritos no Compras.gov.br."""

    if not isinstance(dados, list):
        raise CapturaInvalida("favoritas: era esperada uma lista")
    perguntadas = {c for c in (params.get("compras") or "").split(",") if re.fullmatch(r"\d{17}", c)}
    favoritas = {str(c) for c in dados}
    agora = timezone.now()
    mudou = 0
    for codigo in perguntadas:
        salva = _salva_pelo_codigo(codigo)
        if not salva:
            continue
        favorita = codigo in favoritas
        mudou += int(salva.favorita_no_compras is not favorita)
        salva.favorita_no_compras = favorita
        salva.favorita_conferida_em = agora
        salva.save(update_fields=["favorita_no_compras", "favorita_conferida_em"])
    return {"conferidas": len(perguntadas), "fora": len(perguntadas - favoritas), "mudaram": mudou}


LEITORES = {
    "participacoes": _ler_participacoes,
    "participacao": _ler_participacao,
    "itens": _ler_itens,
    "proposta_do_item": _ler_proposta_do_item,
    "itens_antes_da_sessao": _ler_itens_antes_da_sessao,
    "fase_recursal": _ler_fase_recursal,
    "diligencias": _ler_diligencias,
    "propostas_do_item": _ler_propostas_do_item,
    "favoritas": _ler_favoritas,
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
    """A da Torre; se não houver, a última descartada (que não volta)."""

    todas = OportunidadeSalva.objects.filter(link_plataforma__contains=f"compra={codigo}")
    return todas.filter(removida_em__isnull=True).first() or todas.order_by("-removida_em").first()


def _descartada_da_compra(cnpj: str, ano: str, sequencial: str) -> OportunidadeSalva | None:
    return (
        OportunidadeSalva.objects.filter(
            cnpj_orgao=cnpj, ano_compra=ano, sequencial_compra__in={sequencial, sequencial.zfill(6)}
        )
        .exclude(removida_em__isnull=True)
        .order_by("-removida_em")
        .first()
    )


def _talvez_voltar(salva: OportunidadeSalva) -> None:
    """Descartada só volta para a Torre com convocação."""

    if salva.removida_em is None:
        return
    from apps.licitacoes.lixeira import voltar_por_convocacao

    participacao = getattr(salva, "participacao", None)
    if participacao and participacao.convocacao_em_andamento:
        voltar_por_convocacao(salva, "convocação de remanescente no Compras.gov")
        return
    if item := salva.itens_participados.filter(anexo_solicitado="S").first():
        voltar_por_convocacao(salva, f"convocação para enviar anexo no item {item.numero_item}")


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
    if not salva and chave:
        # Descartada pela lixeira: atualiza em silêncio, nunca recria.
        salva = _descartada_da_compra(*chave)
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
    # Só com a proposta **da empresa** na resposta. Abrir no Compras.gov um
    # item em que ela não entrou devolve o item sem proposta nenhuma — e isso
    # virava item da empresa (59/2026, item 1; corrigido em 09/11/2026).
    # Antes da sessão a proposta vem sem o CNPJ (só a própria empresa a vê):
    # vale se tiver preço. Com CNPJ, tem que ser o da empresa.
    if participante and participante not in cnpjs:
        return 0
    if not participante and not (proposta.get("valores") or {}).get("valorPropostaInicial"):
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
            "sessao_julgamento": int(item.get("numeroSessaoJulgHab") or 1),
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
