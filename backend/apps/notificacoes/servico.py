"""Criar notificação: `avisar(...)`. Repetida (mesma `chave`) não cria outra."""

from __future__ import annotations

from django.db import transaction

from .models import Notificacao


def avisar(tipo: str, titulo: str, *, chave: str, texto: str = "", oportunidade=None, nivel: str = "info") -> bool:
    notificacao, criada = Notificacao.objects.get_or_create(
        chave=chave[:200],
        defaults={
            "tipo": tipo,
            "nivel": nivel,
            "titulo": titulo[:200],
            "texto": texto,
            "oportunidade": oportunidade,
        },
    )
    if criada:
        from .telegram import enviar_telegram, ligado

        if ligado():
            # Depois de gravar, em segundo plano: o Telegram nunca atrasa a Sentinela.
            transaction.on_commit(lambda: enviar_telegram.delay(notificacao.pk))
    return criada
