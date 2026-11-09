"""Tasks Celery do app `licitacoes` — ver docs/ARQUITETURA.md, seção "Assíncrono"."""

from __future__ import annotations

import logging

from celery import shared_task

from .conferencia_diaria import conferir as _conferir
from .sincronia_pncp import sincronizar_pncp as _sincronizar_pncp
from .sincronia_transparencia import sincronizar_transparencia as _sincronizar_transparencia

logger = logging.getLogger(__name__)


@shared_task(name="licitacoes.sincronizar_pncp")
def sincronizar_pncp() -> dict[str, int]:
    """Agendada no Celery Beat todo dia às 8h (migration `0007_agenda_sincronia_pncp`).

    Fina de propósito: a lógica mora em `sincronia_pncp.sincronizar_pncp`,
    também usada pelo `manage.py sincronizar_pncp`.
    """

    resumo = _sincronizar_pncp()
    logger.info("PNCP sincronizado: %s", resumo)
    return resumo


@shared_task(name="licitacoes.sincronizar_transparencia")
def sincronizar_transparencia() -> dict:
    """Agendada no Celery Beat todo dia às 8h10, depois da do PNCP (que traz
    as licitações ganhas às quais os empenhos se ligam). Migration
    `0009_agenda_sincronia_transparencia`."""

    resumo = _sincronizar_transparencia()
    logger.info("Portal da Transparência sincronizado: %s", resumo)
    return resumo


@shared_task(name="licitacoes.conferencia_diaria")
def conferencia_diaria() -> dict:
    """Seg–sex às 7h45 (migration `0018_agenda_conferencia_diaria`): datas e
    situação no PNCP, itens das compras acompanhadas, fim da vigia."""

    resumo = _conferir()
    logger.info("Conferência diária: %s", resumo)
    return resumo

