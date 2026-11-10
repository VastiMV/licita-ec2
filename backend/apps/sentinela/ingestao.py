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
import logging
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
    ItemAcompanhado,
    ItemParticipado,
    OportunidadeSalva,
    ParticipacaoCompra,
    PropostaDoItem,
)
from apps.licitacoes.torre import MODALIDADE_COMPRAS_GOV, proposta_vencedora

logger = logging.getLogger(__name__)

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
    (re.compile(r"/comprasnet-mensagem/v1/mensagens/?$"), "mensagens"),
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
    numero = str(item)
    ItemParticipado.objects.filter(oportunidade=salva, numero_item=numero).update(vigiado_em=timezone.now())
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
    if len(recursos) > len(registro.recursos or []):
        from apps.licitacoes.torre import rotulo_da_compra
        from apps.notificacoes.servico import avisar

        quem = recursos[-1].get("nome") or "outra empresa"
        avisar(
            "recurso",
            f"Recurso · {rotulo_da_compra(salva)} · item {registro.numero_item}",
            texto=f"{quem} entrou com recurso.",
            oportunidade=salva,
            nivel="alerta",
            chave=f"recurso:{registro.pk}:{len(recursos)}",
        )
    registro.recursos = recursos
    registro.prazo_contrarrazao = _data_hora(prazos.get("dataHoraLimiteContrarrazao"))
    registro.decisao_recurso = (revisao or decisao)[:1]
    registro.sessao_julgamento = int(sessao)
    registro.save(update_fields=["recursos", "prazo_contrarrazao", "decisao_recurso", "sessao_julgamento", "atualizado_em"])
    _talvez_voltar(salva)
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
    cnpjs = _cnpjs_da_empresa()
    propostas = [p for p in registro.get("propostasItem") or [] if isinstance(p, dict)]
    da_empresa = next((p for p in propostas if ((p.get("participante") or {}).get("identificacao")) in cnpjs), None)

    # Trava o item até o fim da gravação: com duas Sentinelas ligadas, a
    # segunda espera a primeira terminar e não duplica a lista (09/11/2026).
    participado = (
        ItemParticipado.objects.select_for_update().filter(oportunidade=salva, numero_item=numero).first()
    )
    acompanhado = None
    if not participado:
        acompanhado = (
            ItemAcompanhado.objects.select_for_update().filter(oportunidade=salva, numero_item=numero).first()
        )
        if acompanhado and da_empresa:
            # Rede de segurança (09/11/2026): ele tinha proposta e o Licita
            # não sabia — o item vira dele e a compra volta para a Torre.
            _gravar_item(salva, {**registro, "propostaItem": da_empresa}, cnpjs)
            _marcar_proposta(salva, True)
            participado = ItemParticipado.objects.get(oportunidade=salva, numero_item=numero)
            acompanhado.propostas.all().delete()
            acompanhado.delete()
            acompanhado = None
    if not participado and not acompanhado:
        return {"propostas": 0, "motivo": "item que a empresa não disputa nem acompanha"}

    dono = {"item": participado} if participado else {"acompanhado": acompanhado}
    novas = []
    for proposta in propostas:
        participante = proposta.get("participante") or {}
        valores = proposta.get("valores") or {}
        cnpj = str(participante.get("identificacao") or "")[:14]
        novas.append(
            PropostaDoItem(
                **dono,
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
    PropostaDoItem.objects.filter(**dono).delete()
    PropostaDoItem.objects.bulk_create(novas)
    homologado = registro.get("homologado") is True
    vencedora = proposta_vencedora(novas) if homologado else None

    if acompanhado:
        decidiu = homologado and vencedora is not None and not acompanhado.decidido
        acompanhado.propostas_lidas_em = timezone.now()
        acompanhado.decidido = acompanhado.decidido or (homologado and vencedora is not None)
        acompanhado.save(update_fields=["propostas_lidas_em", "decidido"])
        if decidiu:
            _avisar_resultado(salva, numero, vencedora)
            _talvez_relatorio_completo(salva)
        return {"propostas": len(novas)}

    if da_empresa:
        _gravar_item(salva, {**registro, "propostaItem": da_empresa}, cnpjs)
        participado.refresh_from_db()
    campos = ["vencedor_e_a_empresa", "propostas_lidas_em"]
    if vencedora is not None:
        if participado.vencedor_e_a_empresa is None and not vencedora.da_empresa:
            _avisar_resultado(salva, numero, vencedora)
        participado.vencedor_e_a_empresa = vencedora.da_empresa
        if participado.homologado_em is None:
            # Começo da contagem dos 180 dias da vigia de quem perdeu.
            participado.homologado_em = timezone.localdate()
            campos.append("homologado_em")
    participado.propostas_lidas_em = timezone.now()
    participado.save(update_fields=campos)
    return {"propostas": len(novas)}


def _avisar_resultado(salva: OportunidadeSalva, numero: str, vencedora: PropostaDoItem) -> None:
    """O resultado saiu num item que ele perdeu ou só acompanha → sino."""

    from apps.licitacoes.torre import rotulo_da_compra
    from apps.notificacoes.servico import avisar

    valor = f"R$ {vencedora.valor_final:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if vencedora.valor_final is not None else ""
    partes = [p for p in (vencedora.nome, vencedora.marca, valor) if p]
    avisar(
        "resultado",
        f"Resultado · {rotulo_da_compra(salva)} · item {numero}",
        texto="Ganhou: " + " · ".join(partes),
        oportunidade=salva,
        nivel="info",
        chave=f"resultado:{salva.pk}:{numero}",
    )


def _talvez_relatorio_completo(salva: OportunidadeSalva) -> None:
    from apps.licitacoes.torre import rotulo_da_compra
    from apps.notificacoes.servico import avisar

    itens = salva.itens_acompanhados.all()
    if itens.exists() and not itens.filter(decidido=False).exists():
        avisar(
            "relatorio",
            f"Relatório completo · {rotulo_da_compra(salva)}",
            texto=f"{salva.orgao_nome}: saiu o resultado de todos os {itens.count()} itens.",
            oportunidade=salva,
            nivel="info",
            chave=f"relatorio:{salva.pk}",
        )


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
        if salva.favorita_no_compras is not False and not favorita:
            from apps.licitacoes.torre import rotulo_da_compra
            from apps.notificacoes.servico import avisar

            avisar(
                "favorito",
                f"Fora dos favoritos no Compras.gov · {rotulo_da_compra(salva)}",
                texto=f"{salva.orgao_nome}: está no Licita, mas não nos favoritos. Vai participar?",
                oportunidade=salva,
                nivel="aviso",
                chave=f"favorito:{salva.pk}:{agora:%Y%m%d}",
            )
        salva.favorita_no_compras = favorita
        salva.favorita_conferida_em = agora
        salva.save(update_fields=["favorita_no_compras", "favorita_conferida_em"])
    return {"conferidas": len(perguntadas), "fora": len(perguntadas - favoritas), "mudaram": mudou}


# Categorias da caixa de mensagens (HARs de 07/11/2026).
NIVEL_DA_CATEGORIA = {"830": "alerta", "850": "alerta", "810": "aviso", "840": "info"}
MENSAGEM_RECENTE = dt.timedelta(days=3)


def _ler_mensagens(dados, params, **_) -> dict:
    """A caixa de mensagens do fornecedor — todas as compras juntas
    (convocação 830, pregoeiro 840, recurso 850, impugnação 810). A **lista**
    já traz o texto: nada é aberto, nada fica marcado como lido no
    Compras.gov. Cada mensagem vira um aviso no sino (uma vez só); as antigas
    (mais de 3 dias) não, para a primeira leitura não inundar o sino."""

    from apps.licitacoes.torre import rotulo_da_compra
    from apps.notificacoes.servico import avisar

    if not isinstance(dados, list):
        raise CapturaInvalida("mensagens: era esperada uma lista")
    agora = timezone.now()
    novas = 0
    for m in dados:
        if not isinstance(m, dict) or m.get("excluida") or not m.get("id"):
            continue
        publicada = _data_hora(str(m.get("dataHoraPublicacao") or "").replace(" ", "T"))
        if publicada and agora - publicada > MENSAGEM_RECENTE:
            continue
        codigo = None
        try:
            codigo = (
                f"{int(m['numeroUasg']):06d}{int(m['codigoModalidade']):02d}"
                f"{int(m['numeroCompra']):05d}{int(m['anoCompra']):04d}"
            )
        except (KeyError, TypeError, ValueError):
            pass
        salva = _salva_pelo_codigo(codigo) if codigo else None
        compra = (
            rotulo_da_compra(salva)
            if salva
            else f"{m.get('descricaoModalidade') or 'Compra'} {m.get('numeroCompraFormatado') or ''}".strip()
        )
        uasg = f" · UASG {m.get('numeroUasg')}" if m.get("numeroUasg") and not salva else ""
        novas += int(
            avisar(
                "mensagem",
                f"{m.get('titulo') or 'Mensagem'} · {compra}{uasg}",
                texto=str(m.get("texto") or "")[:1000],
                oportunidade=salva,
                nivel=NIVEL_DA_CATEGORIA.get(str(m.get("categoria") or ""), "info"),
                chave=f"mensagem:{m['id']}",
            )
        )
    return {"mensagens": len(dados), "novas": novas}


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
    "mensagens": _ler_mensagens,
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
        return
    from apps.licitacoes.torre import chamado_de_volta

    # Recurso ou pedido de desconto também trazem de volta (09/11/2026).
    for item in salva.itens_participados.all():
        if chamado_de_volta(item):
            voltar_por_convocacao(salva, f"recurso ou pedido de desconto no item {item.numero_item}")
            return


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
        _pedir_completar(salva)
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
    _pedir_completar(salva)
    return salva, True


def _pedir_completar(salva: OportunidadeSalva) -> None:
    """Sem órgão ou sem itens (o Compras.gov não manda os itens; às vezes nem
    o nome do órgão): pede ao PNCP, em segundo plano, o que a busca teria
    gravado. Sem isso o Cotador abre vazio (10/11/2026, ver
    `apps.licitacoes.completar`). Repete a cada captura até completar."""

    from apps.licitacoes.completar import falta_dados

    if not falta_dados(salva):
        return
    from apps.licitacoes.tasks import completar_salva

    def enfileirar():
        try:
            completar_salva.delay(salva.pk)
        except Exception:  # noqa: BLE001 — fila fora do ar não derruba a captura
            logger.warning("Não deu para pedir o PNCP da salva %s agora", salva.pk)

    transaction.on_commit(enfileirar)


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
    antes = ParticipacaoCompra.objects.filter(oportunidade=salva).first()
    if "dataHoraPrevisaoAbertura" in compra:
        # Vazia = "sem prazo definido" (Butantan, 9/2026): também é notícia.
        valores["sessao_abre_em"] = _data_hora(compra.get("dataHoraPrevisaoAbertura"))
    ParticipacaoCompra.objects.update_or_create(oportunidade=salva, defaults=valores)

    if antes and "sessao_abre_em" in valores and antes.sessao_abre_em and valores["sessao_abre_em"]:
        if antes.sessao_abre_em != valores["sessao_abre_em"]:
            registrar_data_alterada(salva, "abertura da sessão", antes.sessao_abre_em, valores["sessao_abre_em"])
    if antes and (situacao := valores.get("situacao_compra")) and situacao != antes.situacao_compra:
        if situacao == "SU":
            avisar_situacao(salva, "Compra suspensa", "aviso")
        elif situacao in {"RE", "AN"}:
            avisar_situacao(salva, "Compra revogada" if situacao == "RE" else "Compra anulada", "alerta")

    if fim := _data(compra.get("dataHoraFimPropostas")):
        if not salva.data_encerramento_proposta:
            salva.data_encerramento_proposta = fim
            salva.save(update_fields=["data_encerramento_proposta"])
        elif salva.data_encerramento_proposta != fim:
            anterior = salva.data_encerramento_proposta
            salva.data_encerramento_proposta = fim
            salva.save(update_fields=["data_encerramento_proposta"])
            registrar_data_alterada(salva, "prazo da proposta", anterior, fim)


def _quando(valor) -> str:
    if isinstance(valor, dt.datetime):
        return f"{timezone.localtime(valor):%d/%m %H:%M}"
    return f"{valor:%d/%m}"


def registrar_data_alterada(salva: OportunidadeSalva, qual: str, antes, depois) -> None:
    """O órgão mudou a data (09/11/2026): histórico + sino."""

    from apps.licitacoes.torre import rotulo_da_compra
    from apps.notificacoes.servico import avisar

    texto = f"Data alterada pelo órgão ({qual}): {_quando(antes)} → {_quando(depois)}."
    salva.registrar(EventoOportunidadeSalva.Tipo.DATA_ALTERADA, autor=None, descricao=texto)
    avisar(
        "data",
        f"Data alterada · {rotulo_da_compra(salva)}",
        texto=f"{salva.orgao_nome}. {texto}",
        oportunidade=salva,
        nivel="aviso",
        chave=f"data:{salva.pk}:{qual}:{depois}",
    )


def avisar_situacao(salva: OportunidadeSalva, titulo: str, nivel: str) -> None:
    from apps.licitacoes.torre import rotulo_da_compra
    from apps.notificacoes.servico import avisar

    avisar(
        "situacao",
        f"{titulo} · {rotulo_da_compra(salva)}",
        texto=salva.orgao_nome,
        oportunidade=salva,
        nivel=nivel,
        chave=f"situacao:{salva.pk}:{titulo}",
    )


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
    antes = ItemParticipado.objects.filter(oportunidade=salva, numero_item=numero).first()
    campos = {
        "descricao": item.get("descricao") or "",
        "quantidade": _decimal(proposta.get("quantidadeOfertada") or item.get("quantidadeSolicitada")),
        "marca": (proposta.get("marcaFabricante") or "")[:120],
        "modelo": (proposta.get("modeloVersao") or "")[:120],
        "classificacao": proposta.get("classificacao") or None,
        "situacao_proposta": situacao if situacao in SITUACOES_DA_PROPOSTA else "",
        "fase_item": str(item.get("fase") or "")[:4],
        "valor_proposta_inicial": _valor(valores.get("valorPropostaInicial")),
        "valor_lance_final": _valor(valores.get("valorPropostaInicialOuLances")),
        "sessao_julgamento": int(item.get("numeroSessaoJulgHab") or 1),
        "fonte": Fonte.SENTINELA,
    }
    # Convocação e negociação só quando a resposta traz (a lista de propostas
    # de todos não traz a negociação: não pode apagar a que já se sabe).
    if "situacaoUltimaSolicitacaoAnexos" in proposta or antes is None:
        campos["anexo_solicitado"] = anexo if anexo in {"S", "P", "E"} else ""
    if "situacaoUltimaNegociacao" in proposta or antes is None:
        campos["negociacao"] = str(proposta.get("situacaoUltimaNegociacao") or "")[:1]
        campos["negociacao_texto"] = proposta.get("justificativaUltimaNegociacao") or ""
    registro, _ = ItemParticipado.objects.update_or_create(oportunidade=salva, numero_item=numero, defaults=campos)
    _avisar_chamado(salva, registro, antes)
    return 1


def _avisar_chamado(salva: OportunidadeSalva, item: ItemParticipado, antes: ItemParticipado | None) -> None:
    """Convocação ou pedido de desconto que acabou de aparecer → sino (vermelho)."""

    from apps.licitacoes.torre import rotulo_da_compra
    from apps.notificacoes.servico import avisar

    compra = rotulo_da_compra(salva)
    if item.anexo_solicitado == "S" and (antes is None or antes.anexo_solicitado != "S"):
        avisar(
            "convocacao",
            f"Convocação · {compra} · item {item.numero_item}",
            texto=f"{salva.orgao_nome}: o pregoeiro pediu o envio de anexo.",
            oportunidade=salva,
            nivel="alerta",
            chave=f"convocacao:{item.pk}:{timezone.localdate()}",
        )
    aberta = bool(item.negociacao) and item.negociacao != "E"
    if aberta and (antes is None or not (antes.negociacao and antes.negociacao != "E")):
        avisar(
            "desconto",
            f"Pedido de desconto · {compra} · item {item.numero_item}",
            texto=item.negociacao_texto or salva.orgao_nome,
            oportunidade=salva,
            nivel="alerta",
            chave=f"desconto:{item.pk}:{timezone.localdate()}",
        )


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
