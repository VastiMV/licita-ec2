"""Tasks Celery do app `sentinela`."""

from __future__ import annotations

from celery import shared_task

from .silencio import conferir_silencio as _conferir_silencio


@shared_task(name="sentinela.conferir_silencio")
def conferir_silencio() -> bool:
    """A cada 10 min (migration `0004_agenda_conferir_silencio`): Sentinela
    sem ler há 30 min em horário de trabalho → sino + Telegram (GEN-73)."""

    return _conferir_silencio()
