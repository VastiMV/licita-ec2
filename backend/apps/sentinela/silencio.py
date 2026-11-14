"""Alarme de silêncio da Sentinela (GEN-73, 14/11/2026).

Caso real: de 11/11 às 22h42 a 14/11 às 10h50 a Sentinela **não leu nada**
do Compras.gov — e o topo do Licita ficou verde, porque ela mandava "ok" a
cada 3 minutos (havia uma aba do Compras.gov aberta, mas a ronda falhava
calada). As mensagens do pregoeiro só chegaram dois dias depois.

A regra aqui não depende da extensão — pega até falha que ninguém previu:
em horário de trabalho, **30 minutos sem nenhuma leitura** (captura) é
problema. A contagem começa no início do expediente de hoje (8h), então na
segunda às 8h30 o fim de semana não conta.

- `minutos_sem_leitura` → usado pelo topo do Licita (`estado.py`): âmbar,
  "ligada, mas sem ler".
- `conferir_silencio` → tarefa do Celery Beat a cada 10 min: aviso no sino e
  no Telegram, **um por episódio** (a chave da notificação é o começo do
  silêncio).
"""

from __future__ import annotations

import datetime as dt

from django.utils import timezone

from .estado import HORARIO, em_horario_de_trabalho
from .models import Pulso

MINUTOS_SEM_LEITURA = 30
MINUTOS_LIGADA = 15  # sinal de vida nesse intervalo = o Chrome está ligado


def _inicio_do_expediente(agora: dt.datetime) -> dt.datetime:
    local = timezone.localtime(agora)
    return local.replace(hour=HORARIO[0], minute=0, second=0, microsecond=0)


def desde_quando_sem_leitura(agora: dt.datetime) -> dt.datetime:
    """A última leitura, ou o começo do expediente de hoje (o que for depois)."""

    inicio = _inicio_do_expediente(agora)
    ultima = Pulso.objects.exclude(captura="").first()
    return max(ultima.recebido_em, inicio) if ultima else inicio


def minutos_sem_leitura(agora: dt.datetime | None = None) -> int | None:
    """Minutos sem leitura, em horário de trabalho. `None` fora dele."""

    agora = agora or timezone.now()
    if not em_horario_de_trabalho(agora):
        return None
    return max(0, int((agora - desde_quando_sem_leitura(agora)).total_seconds() // 60))


def ligada(agora: dt.datetime) -> bool:
    return Pulso.objects.filter(recebido_em__gte=agora - dt.timedelta(minutes=MINUTOS_LIGADA)).exists()


def conferir_silencio(agora: dt.datetime | None = None) -> bool:
    """Avisa (sino + Telegram) se a Sentinela está sem ler. `True` se avisou agora."""

    from apps.notificacoes.servico import avisar

    agora = agora or timezone.now()
    minutos = minutos_sem_leitura(agora)
    if minutos is None or minutos < MINUTOS_SEM_LEITURA:
        return False
    desde = timezone.localtime(desde_quando_sem_leitura(agora))
    if ligada(agora):
        titulo = f"A Sentinela está ligada, mas não lê o Compras.gov há {minutos} min"
        texto = (
            "Mensagens do pregoeiro e mudanças na Torre não estão chegando. Confira no Chrome: "
            "a aba do Compras.gov aberta na área do fornecedor, logada — e dê F5 nela."
        )
    else:
        titulo = f"A Sentinela está parada: nenhuma notícia dela há {minutos} min"
        texto = (
            "Mensagens do pregoeiro e mudanças na Torre não estão chegando. Confira se o Chrome "
            "está aberto, com a Sentinela ligada e a aba do Compras.gov logada."
        )
    return avisar(
        "sentinela",
        titulo,
        chave=f"sentinela-sem-leitura-{desde:%Y%m%d%H%M}",
        texto=texto,
        nivel="alerta",
    )
