"""Acesso de **leitura** ao Licita por chave (pedido da operação, 09/11/2026).

Para o assistente conferir as telas depois de cada publicação sem senha de
ninguém: quem manda `X-Licita-Leitura-Token: <LEITURA_CHAVE>` é tratado como
o usuário "Leitura" — **só em GET/HEAD/OPTIONS**. Em qualquer escrita a chave
é ignorada (a requisição segue sem usuário e o Licita responde 401).

- A chave mora só no `.env` do servidor e no cofre do ambiente do assistente
  (o proxy injeta o cabeçalho); nunca passa pelo chat.
- O usuário "Leitura" é inativo: não faz login, não recebe token, não aparece
  como alguém da equipe. Desligar: apagar `LEITURA_CHAVE` do `.env`.
"""

from __future__ import annotations

import hmac

from rest_framework.authentication import BaseAuthentication
from rest_framework.permissions import SAFE_METHODS

from config.settings.environment import env

from .models import User

CABECALHO = "HTTP_X_LICITA_LEITURA_TOKEN"
EMAIL_DO_LEITOR = "leitura@licita.interno"


def leitor() -> User:
    usuario, criado = User.objects.get_or_create(
        email=EMAIL_DO_LEITOR, defaults={"nome": "Leitura (conferência)", "is_active": False}
    )
    if criado:
        usuario.set_unusable_password()
        usuario.save(update_fields=["password"])
    return usuario


def _chave_recebida(request) -> str:
    """A chave vem em `X-Licita-Leitura-Token` ou em `Authorization: Bearer
    <chave>` (o formato que o cofre do ambiente do assistente aceita). No
    segundo caso, um token de login comum nunca é igual à chave: segue para
    o JWT normalmente."""

    if direta := request.META.get(CABECALHO, ""):
        return direta
    tipo, _, valor = request.META.get("HTTP_AUTHORIZATION", "").partition(" ")
    return valor.strip() if tipo.lower() == "bearer" else ""


class ChaveDeLeitura(BaseAuthentication):
    def authenticate(self, request):
        recebida = _chave_recebida(request)
        esperada = env.leitura_chave
        if not recebida or not esperada or request.method not in SAFE_METHODS:
            return None
        if not hmac.compare_digest(recebida.encode(), esperada.encode()):
            return None
        return leitor(), None

    def authenticate_header(self, request) -> str:
        # Vem primeiro na lista: é ela que decide 401 × 403. Responde como o
        # JWT, para o "sessão expirou → renovar" do Licita continuar igual.
        return 'Bearer realm="api"'
