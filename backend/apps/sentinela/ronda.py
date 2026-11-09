"""A ronda da Sentinela: o que ela consulta **sozinha** no Compras.gov.br.

Hoje é uma consulta só, que **não pede captcha**: a lista de propostas de
todos os participantes de um item (`em-selecao-fornecedores/itens/{n}/propostas`).
Só para os itens em que a empresa participa e que já passaram da disputa
(têm posição). É dela que saem o 👍/🟠/👎 da Torre e o relatório da licitação.

Ritmo de gente (docs/SENTINELA.md): no máximo `POR_RONDA` itens por vez,
os mais atrasados primeiro, e cada item no máximo a cada `INTERVALO`.
Item já decidido (homologado para alguém) é lido **uma vez** depois da
decisão e sai da ronda.

A extensão faz a consulta na aba do Compras.gov, com a sessão da própria
página, e manda a resposta para `captura/` — a leitura é a mesma de quando
o Carlinhos abre a tela (`ingestao._ler_propostas_do_item`).
"""

from __future__ import annotations

import datetime as dt
import re

from django.db.models import F, Q
from django.utils import timezone

from apps.licitacoes.models import ItemParticipado

BASE = "/comprasnet-fase-externa/v1/compras"
CODIGO = re.compile(r"compra=(\d{17})")
INTERVALO = dt.timedelta(hours=2)
POR_RONDA = 15


def caminho_das_propostas(codigo: str, numero_item: str) -> str:
    return f"{BASE}/{codigo}/em-selecao-fornecedores/itens/{numero_item}/propostas?ordenacao-propostas=V"


def consultas(agora: dt.datetime | None = None) -> list[str]:
    agora = agora or timezone.now()
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
        achado = CODIGO.search(item.oportunidade.link_plataforma or "")
        if not achado or not re.fullmatch(r"[A-Za-z0-9-]+", item.numero_item):
            continue
        caminhos.append(caminho_das_propostas(achado.group(1), item.numero_item))
        if len(caminhos) >= POR_RONDA:
            break
    return caminhos
