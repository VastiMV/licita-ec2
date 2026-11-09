"""Criar notificação: `avisar(...)`. Repetida (mesma `chave`) não cria outra."""

from __future__ import annotations

from .models import Notificacao


def avisar(tipo: str, titulo: str, *, chave: str, texto: str = "", oportunidade=None, nivel: str = "info") -> bool:
    _, criada = Notificacao.objects.get_or_create(
        chave=chave[:200],
        defaults={
            "tipo": tipo,
            "nivel": nivel,
            "titulo": titulo[:200],
            "texto": texto,
            "oportunidade": oportunidade,
        },
    )
    return criada
