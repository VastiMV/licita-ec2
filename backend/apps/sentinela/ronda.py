"""A ronda da Sentinela: o que ela consulta **sozinha** no Compras.gov.br, a
cada 10 minutos em horário de trabalho — **só endereços que não pedem
captcha**, na aba do Compras.gov, com a sessão da própria página. Cada
resposta volta para `captura/` (a mesma leitura de quando o Carlinhos abre a
tela).

Em ordem de prioridade, até `MAXIMO` consultas por ronda (ritmo de gente):

1. **Favoritos** (09/11/2026): numa consulta só, quais compras de Preparar
   ainda estão nos favoritos do Compras.gov. A que saiu de lá ganha o aviso
   "fora dos favoritos no Compras.gov" (Lavras, 60/2027).
2. Para cada item vivo da empresa numa compra depois da sessão (fase 3 ou 4):
   a **proposta** (situação, posição, pedido de desconto, convocação). Nos
   itens em que ela está na frente (até 2º) ou já aceita/habilitada, também
   a **fase recursal** (o recurso do 56/2026 item 22 que ninguém viu) e as
   **diligências**. Descartadas entram só com a proposta: é dela que vem a
   convocação que as traz de volta.
3. As **propostas de todos os participantes** (👍/🟠/👎 e o relatório): no
   máximo `POR_RONDA` itens, os mais atrasados primeiro, cada um no máximo a
   cada `INTERVALO`; item decidido é lido uma vez depois da decisão e sai.
4. **Vigia diária** (09/11/2026), na primeira ronda do dia (se o computador
   ligar às 10h, é às 10h): os itens que ele **perdeu** (ou que estão em
   Encerradas/Descartadas) — a proposta dele (convocação) e o recurso —, até
   a ata/contrato do concorrente ou 180 dias depois da homologação; e os
   itens das compras que ele só **acompanha** (o relatório para "xeretar").
"""

from __future__ import annotations

import datetime as dt
import re

from django.db.models import F, Q
from django.utils import timezone

from apps.empresas.models import Empresa
from apps.licitacoes.models import ItemAcompanhado, ItemParticipado, OportunidadeSalva

BASE = "/comprasnet-fase-externa/v1/compras"
FAVORITAS = "/comprasnet-oportunidade/v1/compras/favoritas/dentre-opcoes"
CODIGO = re.compile(r"compra=(\d{17})")
NUMERO_SEGURO = re.compile(r"[A-Za-z0-9-]+")
FASES_DEPOIS_DA_SESSAO = {"3", "4"}
PERDIDO = ["1", "2", "9", "5"]
JA_JULGADO = {"3", "4", "6"}
INTERVALO = dt.timedelta(hours=2)
POR_RONDA = 15
MAXIMO = 60
FAVORITAS_POR_CONSULTA = 30


def caminho_das_propostas(codigo: str, numero_item: str) -> str:
    return f"{BASE}/{codigo}/em-selecao-fornecedores/itens/{numero_item}/propostas?ordenacao-propostas=V"


def _codigo(salva) -> str | None:
    achado = CODIGO.search(salva.link_plataforma or "")
    return achado.group(1) if achado else None


def _favoritas() -> list[str]:
    """As compras do Compras.gov.br que ainda estão em Preparar."""

    from apps.licitacoes.torre import ESTAGIO_DA_ETAPA, avaliar

    hoje = timezone.localdate()
    codigos = []
    salvas = (
        OportunidadeSalva.objects.ativas()
        .filter(link_plataforma__contains="compra=")
        .select_related("cotacao", "participacao", "proposta")
        .prefetch_related("itens_participados__propostas", "documentos_financeiros", "entregas")
    )
    for salva in salvas:
        cartao, saida = avaliar(salva, hoje)
        if saida or ESTAGIO_DA_ETAPA[cartao["etapa"]] != "preparar":
            continue
        if codigo := _codigo(salva):
            codigos.append(codigo)
    return [
        f"{FAVORITAS}?compras={','.join(codigos[i : i + FAVORITAS_POR_CONSULTA])}"
        for i in range(0, len(codigos), FAVORITAS_POR_CONSULTA)
    ]


VIGIA_MAXIMA = dt.timedelta(days=180)
POR_DIA = 40


def _inicio_do_dia(agora: dt.datetime) -> dt.datetime:
    local = timezone.localtime(agora)
    return local.replace(hour=0, minute=0, second=0, microsecond=0)


def _vigia_diaria(agora: dt.datetime) -> list[str]:
    """Itens perdidos ainda vigiados que não foram conferidos hoje."""

    from apps.licitacoes.torre import etapa_do_item

    cnpjs = list(Empresa.objects.filter(ativa=True).values_list("cnpj", flat=True))
    if not cnpjs:
        return []
    cnpj = cnpjs[0]
    hoje = timezone.localdate(agora)
    itens = (
        ItemParticipado.objects.filter(vigia_encerrada_em__isnull=True, oportunidade__link_plataforma__contains="compra=")
        .filter(Q(vigiado_em__isnull=True) | Q(vigiado_em__lt=_inicio_do_dia(agora)))
        .select_related("oportunidade")
        .prefetch_related("propostas")
        .order_by(F("vigiado_em").asc(nulls_first=True), "id")
    )
    caminhos: list[str] = []
    for item in itens:
        perdido = etapa_do_item(item, [], [], hoje).etapa is None
        if not (perdido or item.oportunidade.removida_em is not None):
            continue  # vivo: a ronda de 10 em 10 minutos já cuida
        if item.homologado_em and hoje - item.homologado_em > VIGIA_MAXIMA:
            ItemParticipado.objects.filter(pk=item.pk).update(
                vigia_encerrada_em=agora, vigia_motivo="180 dias depois da homologação"
            )
            continue
        codigo, n = _codigo(item.oportunidade), item.numero_item
        if not codigo or not NUMERO_SEGURO.fullmatch(n):
            continue
        caminhos.append(f"{BASE}/{codigo}/em-selecao-fornecedores/participacoes/{cnpj}/itens/{n}/propostas?filtro=2")
        caminhos.append(f"{BASE}/{codigo}/itens/{n}/fase-recursal-fornecedor/{item.sessao_julgamento or 1}")
        if len(caminhos) >= POR_DIA:
            break
    return caminhos


def _acompanhados(agora: dt.datetime) -> list[str]:
    """As compras que ele só acompanha: as propostas de cada item, 1x por dia,
    até o resultado sair."""

    itens = (
        ItemAcompanhado.objects.filter(decidido=False, oportunidade__removida_em__isnull=True)
        .filter(Q(propostas_lidas_em__isnull=True) | Q(propostas_lidas_em__lt=_inicio_do_dia(agora)))
        .select_related("oportunidade")
        .order_by(F("propostas_lidas_em").asc(nulls_first=True), "id")
    )
    caminhos: list[str] = []
    for item in itens:
        codigo = _codigo(item.oportunidade)
        if codigo and NUMERO_SEGURO.fullmatch(item.numero_item):
            caminhos.append(caminho_das_propostas(codigo, item.numero_item))
        if len(caminhos) >= POR_RONDA:
            break
    return caminhos


def _da_empresa() -> list[str]:
    cnpjs = list(Empresa.objects.filter(ativa=True).values_list("cnpj", flat=True))
    if not cnpjs:
        return []
    cnpj = cnpjs[0]
    caminhos: list[str] = []
    from apps.licitacoes.torre import etapa_do_item

    hoje = timezone.localdate()
    itens = (
        ItemParticipado.objects.filter(oportunidade__participacao__fase_compra__in=FASES_DEPOIS_DA_SESSAO)
        .exclude(vencedor_e_a_empresa=False)
        .exclude(situacao_proposta__in=PERDIDO)
        .select_related("oportunidade")
        .prefetch_related("propostas")
        .order_by("oportunidade_id", "numero_item")
    )
    for item in itens:
        if etapa_do_item(item, [], [], hoje).etapa is None:
            continue  # perdido (ex.: 1º já habilitado): vigia diária
        codigo, n = _codigo(item.oportunidade), item.numero_item
        if not codigo or not NUMERO_SEGURO.fullmatch(n):
            continue
        caminhos.append(f"{BASE}/{codigo}/em-selecao-fornecedores/participacoes/{cnpj}/itens/{n}/propostas?filtro=2")
        if item.oportunidade.removida_em is not None:
            continue  # descartada: só o que pode ser convocação
        na_frente = item.classificacao is not None and item.classificacao <= 2
        if na_frente or item.situacao_proposta in JA_JULGADO:
            caminhos.append(f"{BASE}/{codigo}/itens/{n}/fase-recursal-fornecedor/{item.sessao_julgamento or 1}")
            caminhos.append(f"{BASE}/{codigo}/itens/{n}/participacoes/{cnpj}/diligencias")
    return caminhos


def _propostas_de_todos(agora: dt.datetime) -> list[str]:
    itens = (
        ItemParticipado.objects.filter(
            oportunidade__removida_em__isnull=True,
            oportunidade__link_plataforma__contains="compra=",
            classificacao__isnull=False,
        )
        .filter(
            Q(propostas_lidas_em__isnull=True)
            | Q(vencedor_e_a_empresa__isnull=True, propostas_lidas_em__lt=agora - INTERVALO)
        )
        .select_related("oportunidade")
        .order_by(F("propostas_lidas_em").asc(nulls_first=True), "oportunidade_id", "id")
    )
    caminhos: list[str] = []
    for item in itens:
        codigo = _codigo(item.oportunidade)
        if not codigo or not NUMERO_SEGURO.fullmatch(item.numero_item):
            continue
        caminhos.append(caminho_das_propostas(codigo, item.numero_item))
        if len(caminhos) >= POR_RONDA:
            break
    return caminhos


def consultas(agora: dt.datetime | None = None) -> list[str]:
    agora = agora or timezone.now()
    todas = _favoritas() + _da_empresa() + _vigia_diaria(agora) + _propostas_de_todos(agora) + _acompanhados(agora)
    return list(dict.fromkeys(todas))[:MAXIMO]  # sem repetir, na ordem
