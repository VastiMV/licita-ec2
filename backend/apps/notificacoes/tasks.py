"""Tarefas do Celery deste app.

O worker só carrega tarefas de `tasks.py` (`autodiscover_tasks`, em
`config/celery.py`). A do Telegram mora em `telegram.py`; sem esta linha o
worker jogava fora todo aviso ("unregistered task") — GEN-103, 19/11/2026.
"""

from .telegram import enviar_telegram

__all__ = ["enviar_telegram"]
