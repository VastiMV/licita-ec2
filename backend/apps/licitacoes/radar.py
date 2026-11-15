"""O Radar (GEN-68, 14/11/2026): busca automática de compras parecidas.

**Por quê:** o Carlinhos salva dezenas de oportunidades por mês, de itens que
se repetem. O Radar faz a busca por ele, todo dia às 8h e às 18h
(migration `0023_agenda_radar`), e deixa as compras achadas numa lista.

Regras da operação (cartão GEN-68 e respostas de 14/11/2026):

1. **Base** = os itens das oportunidades **salvas nos últimos 30 dias** + os
   itens que a Inside **ganhou** (qualquer data). O que foi só digitado na
   busca não conta (o Licita não guarda o histórico da busca).
2. **Onde:** todos os portais (busca textual do PNCP, sem filtro de
   plataforma) e o Brasil todo. A tela tem filtro de UF.
3. **O quê:** compras **recebendo proposta**, publicadas desde a rodada
   anterior (janela de `JANELA_DIAS`), que não estão salvas no Licita (nem
   tiradas da lista: quem tirou já decidiu).
4. **Quanto tempo:** a sugestão fica **7 dias ou até a abertura da
   disputa** (o prazo da proposta no PNCP), o que vier primeiro, e some
   sozinha (ajuste da operação, 14/11/2026). No dia da abertura ela ainda
   aparece: a proposta pode ser enviada até a hora da sessão, e o Licita só
   guarda o dia.
5. **Aviso:** só o número no botão Radar do topo.

**"Parecido" (decisão técnica):** a descrição do item vira o termo da busca
pelo **tipo do catálogo** (PDM: "Ração suplementar para aves" → o nome do
PDM, como em `mercado.achar_pdm`); sem PDM, as primeiras palavras da
descrição. Ganho vem antes de salvo, e a rodada tem um teto de termos
(`MAX_TERMOS`) para não estourar o PNCP (ele limita por IP).
"""

from __future__ import annotations

import datetime as dt
import logging
from decimal import Decimal

from django.db.models import Exists, OuterRef
from django.utils import timezone

from apps.integracoes.clients.pncp import PncpClient, PncpClientError

from .mercado import achar_pdm, normalizar
from .models import ItemParticipado, OportunidadeSalva, SugestaoRadar, montar_texto_busca

logger = logging.getLogger(__name__)

DIAS_DA_BASE = 30
DIAS_NO_RADAR = 7
JANELA_DIAS = 2  # publicadas de anteontem para cá: as rodadas se sobrepõem
MAX_TERMOS = 30
PALAVRAS_SEM_PDM = 4


def _termo(descricao: str) -> str:
    """O que se procura no PNCP para uma descrição de item."""

    pdm = achar_pdm(descricao)
    if pdm:
        return pdm.nome_pdm
    return " ".join(normalizar(descricao).lower().split()[:PALAVRAS_SEM_PDM])


def termos_da_base(hoje: dt.date | None = None) -> list[tuple[str, str, bool]]:
    """`(termo, descrição de origem, por_ganho)`, sem repetir termo. Ganho
    primeiro; no máximo `MAX_TERMOS`."""

    hoje = hoje or timezone.localdate()
    inicio = timezone.make_aware(dt.datetime.combine(hoje - dt.timedelta(days=DIAS_DA_BASE), dt.time.min))
    descricoes: list[tuple[str, bool]] = [
        (d, True)
        for d in ItemParticipado.objects.filter(vencedor_e_a_empresa=True)
        .exclude(descricao="")
        .order_by("-atualizado_em")
        .values_list("descricao", flat=True)
    ]
    for itens in (
        OportunidadeSalva.objects.ativas().filter(criada_em__gte=inicio).order_by("-criada_em").values_list("itens", flat=True)
    ):
        for item in itens or []:
            if descricao := (item.get("descricao_resumida") or "").strip():
                descricoes.append((descricao, False))

    vistos: set[str] = set()
    termos: list[tuple[str, str, bool]] = []
    for descricao, por_ganho in descricoes:
        termo = _termo(descricao)
        chave = normalizar(termo)
        if not chave or chave in vistos:
            continue
        vistos.add(chave)
        termos.append((termo, descricao, por_ganho))
        if len(termos) >= MAX_TERMOS:
            break
    return termos


def _data(valor) -> dt.date | None:
    if not isinstance(valor, str):
        return None
    try:
        return dt.date.fromisoformat(valor[:10])
    except ValueError:
        return None


def _valor_total(itens: list[dict]) -> Decimal | None:
    valores = [i.get("valor_total") for i in itens]
    if not valores or any(v is None for v in valores):
        return None
    return Decimal(str(sum(valores)))


def _chave(item: dict) -> tuple[str, str, str]:
    return (
        str(item.get("contratacao_cnpj_orgao") or ""),
        str(item.get("contratacao_ano_compra") or ""),
        str(item.get("contratacao_sequencial_compra") or ""),
    )


def _ja_conhecidas() -> set[tuple[str, str, str]]:
    """Salvas (inclusive as tiradas da lista) e as que já estão no Radar."""

    conhecidas = set(
        OportunidadeSalva.objects.values_list("cnpj_orgao", "ano_compra", "sequencial_compra")
    )
    conhecidas |= set(SugestaoRadar.objects.values_list("cnpj_orgao", "ano_compra", "sequencial_compra"))
    return conhecidas


def rodar(hoje: dt.date | None = None, pncp: PncpClient | None = None) -> dict[str, int]:
    """Uma rodada do Radar: limpa as vencidas e procura as novas."""

    from .services import _buscar_no_pncp

    hoje = hoje or timezone.localdate()
    resumo = {"termos": 0, "novas": 0, "removidas": limpar(hoje), "falhas": 0}
    termos = termos_da_base(hoje)
    resumo["termos"] = len(termos)
    if not termos:
        return resumo

    proprio = pncp is None
    cliente = pncp or PncpClient()
    conhecidas = _ja_conhecidas()
    try:
        for termo, origem, por_ganho in termos:
            try:
                achados = _buscar_no_pncp(
                    termo,
                    data_inicial=(hoje - dt.timedelta(days=JANELA_DIAS)).isoformat(),
                    data_final=hoje.isoformat(),
                    codigo_modalidade="",
                    uf=None,
                    codigo_unidade=None,
                    plataforma=None,
                    pncp_client=cliente,
                ) or []
            except PncpClientError:
                resumo["falhas"] += 1
                logger.warning('Radar: o PNCP falhou na busca de "%s"', termo)
                continue

            por_compra: dict[tuple[str, str, str], list[dict]] = {}
            for item in achados:
                chave = _chave(item)
                if all(chave) and chave not in conhecidas:
                    por_compra.setdefault(chave, []).append(item)

            for chave, itens in por_compra.items():
                primeiro = itens[0]
                prazo = _data(primeiro.get("contratacao_data_encerramento_proposta"))
                if prazo and prazo < hoje:
                    continue
                objeto = primeiro.get("contratacao_objeto") or ""
                SugestaoRadar.objects.create(
                    cnpj_orgao=chave[0],
                    ano_compra=chave[1],
                    sequencial_compra=chave[2],
                    objeto=objeto,
                    orgao_nome=(primeiro.get("contratacao_orgao_nome") or "")[:255],
                    uasg=primeiro.get("contratacao_uasg") or "",
                    uf=(primeiro.get("contratacao_uf") or "")[:2],
                    municipio=(primeiro.get("contratacao_municipio") or "")[:255],
                    modalidade=(primeiro.get("contratacao_modalidade") or "")[:120],
                    data_publicacao=_data(primeiro.get("contratacao_data_publicacao")),
                    data_encerramento_proposta=prazo,
                    valor_total_estimado=_valor_total(itens),
                    plataforma_id=primeiro.get("plataforma_id") or "",
                    link_plataforma=primeiro.get("link_plataforma") or "",
                    link_pncp=primeiro.get("link_pncp") or "",
                    itens=itens,
                    texto_busca=montar_texto_busca(objeto, itens),
                    parecido_com=origem[:255],
                    por_ganho=por_ganho,
                    expira_em=_expira_em(hoje, prazo),
                )
                conhecidas.add(chave)
                resumo["novas"] += 1
    finally:
        if proprio:
            cliente.close()
    return resumo


def _expira_em(hoje: dt.date, prazo: dt.date | None) -> dt.date:
    """O dia em que some: 7 dias depois de achada, ou o dia seguinte à
    abertura da disputa — o que vier primeiro."""

    sete_dias = hoje + dt.timedelta(days=DIAS_NO_RADAR)
    return min(sete_dias, prazo + dt.timedelta(days=1)) if prazo else sete_dias


def limpar(hoje: dt.date | None = None) -> int:
    """Apaga as que fizeram 7 dias no Radar ou cuja disputa já abriu."""

    hoje = hoje or timezone.localdate()
    apagadas, _ = SugestaoRadar.objects.filter(expira_em__lte=hoje).delete()
    return apagadas


def visiveis(hoje: dt.date | None = None):
    """As que a tela mostra: dentro dos 7 dias, prazo aberto, e que ninguém
    salvou depois (salvar pelo card tira do Radar)."""

    hoje = hoje or timezone.localdate()
    salvas = OportunidadeSalva.objects.filter(
        cnpj_orgao=OuterRef("cnpj_orgao"),
        ano_compra=OuterRef("ano_compra"),
        sequencial_compra=OuterRef("sequencial_compra"),
    )
    return (
        SugestaoRadar.objects.filter(expira_em__gt=hoje)
        .exclude(data_encerramento_proposta__lt=hoje)
        .exclude(Exists(salvas))
    )
