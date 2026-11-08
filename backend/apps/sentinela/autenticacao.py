"""Quem fala com a API da Sentinela é a extensão, não uma pessoa: ela se
identifica com a chave `SENTINELA_CHAVE` no cabeçalho `X-Sentinela-Chave`.

Nunca a senha de ninguém. A chave só abre as rotas da Sentinela.
"""

from __future__ import annotations

import hmac

from rest_framework.permissions import BasePermission

from config.settings.environment import env

CABECALHO = "HTTP_X_SENTINELA_CHAVE"


class ChaveDaSentinela(BasePermission):
    message = "Chave da Sentinela ausente ou errada."

    def has_permission(self, request, view) -> bool:
        esperada = env.sentinela_chave
        recebida = request.META.get(CABECALHO, "")
        return bool(esperada) and hmac.compare_digest(recebida.encode(), esperada.encode())
