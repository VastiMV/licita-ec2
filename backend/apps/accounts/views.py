"""
Endpoints de autenticação — ver docs/ARQUITETURA.md, seção "Autenticação",
para o fluxo completo (por que o `refresh` vive num cookie `httpOnly` e não
no corpo da resposta, por que só `/api/auth/refresh/` fica sujeito a CSRF).
"""

from __future__ import annotations

import time

from django.conf import settings
from django.core import signing
from django.http import HttpResponse, HttpResponseRedirect
from django.middleware.csrf import get_token
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from config.settings.environment import env

from .models import User
from .serializers import LoginSerializer

REFRESH_COOKIE_NAME = "refresh"
# Restrito a /api/auth/ — o cookie não precisa (e não deve) ir em requests
# para o resto da API, que se autentica só pelo header Authorization.
REFRESH_COOKIE_PATH = "/api/auth/"


def _set_refresh_cookie(response: HttpResponse, refresh: str) -> None:
    lifetime = settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"]
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        refresh,
        max_age=int(lifetime.total_seconds()),
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="Lax",
    )


def _clear_refresh_cookie(response: HttpResponse) -> None:
    response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)


class LoginView(APIView):
    """`POST /api/auth/login/` — recebe `email`/`password`, devolve `access` no corpo."""

    permission_classes = [AllowAny]

    def post(self, request: Request, *args, **kwargs) -> Response:
        serializer = LoginSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            raise InvalidToken(e.args[0]) from e

        # Garante o cookie `csrftoken` já nesta resposta: é o único jeito do
        # SPA ter o token disponível antes do primeiro request a
        # `/api/auth/refresh/` — ver `RefreshView`.
        get_token(request)

        response = Response({"access": serializer.validated_data["access"]})
        _set_refresh_cookie(response, serializer.validated_data["refresh"])
        return response


def _login_vencido(raw_refresh: str) -> bool:
    """O login passou de `sessao_maxima_horas` desde a entrada? Token sem a
    hora da entrada (emitido antes desta regra) também vence: entra de novo."""

    try:
        login_em = RefreshToken(raw_refresh).payload.get("login_em")
    except TokenError:
        return False  # inválido/expirado: o TokenRefreshSerializer responde
    if not login_em:
        return True
    return time.time() - int(login_em) > env.sessao_maxima_horas * 3600


class RefreshView(APIView):
    """
    `POST /api/auth/refresh/` — única prova de identidade aqui é o cookie
    `httpOnly` do `refresh` (não há header `Authorization`), então é o único
    endpoint de auth que continua sujeito ao `CsrfViewMiddleware` de
    verdade: `as_view()` desfaz a isenção de CSRF que o DRF aplica por
    padrão a toda `APIView`.
    """

    permission_classes = [AllowAny]

    @classmethod
    def as_view(cls, **kwargs):
        view = super().as_view(**kwargs)
        view.csrf_exempt = False
        return view

    def post(self, request: Request, *args, **kwargs) -> Response:
        raw_refresh = request.COOKIES.get(REFRESH_COOKIE_NAME)
        if not raw_refresh:
            raise InvalidToken("Sessão expirada.")

        if _login_vencido(raw_refresh):
            response = Response(
                {"detail": "Sessão encerrada: o login vale 12 horas. Entre de novo."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
            _clear_refresh_cookie(response)
            return response

        serializer = TokenRefreshSerializer(data={"refresh": raw_refresh})
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            response = Response({"detail": str(e)}, status=status.HTTP_401_UNAUTHORIZED)
            _clear_refresh_cookie(response)
            return response

        response = Response({"access": serializer.validated_data["access"]})
        # ROTATE_REFRESH_TOKENS=True (settings) sempre devolve um "refresh" novo aqui.
        _set_refresh_cookie(response, serializer.validated_data.get("refresh", raw_refresh))
        return response


class LogoutView(APIView):
    """`POST /api/auth/logout/` — invalida o `refresh` (blacklist) e limpa o cookie."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, *args, **kwargs) -> Response:
        raw_refresh = request.COOKIES.get(REFRESH_COOKIE_NAME)
        if raw_refresh:
            try:
                RefreshToken(raw_refresh).blacklist()
            except TokenError:
                pass  # já expirado/blacklisted — o objetivo (sair) já está feito

        response = Response(status=status.HTTP_204_NO_CONTENT)
        _clear_refresh_cookie(response)
        response.delete_cookie(DOCS_COOKIE_NAME, path=DOCS_COOKIE_PATH)
        return response


# ---------- o passe da documentação (GEN-63, 10/11/2026) ----------
#
# O site da documentação (/documentacao) é estático, servido por outra
# imagem, atrás do mesmo login do Licita. O navegador não manda o token do
# Licita (fica na memória da página) nem o cookie do refresh (só vale em
# /api/auth/) para /documentacao — por isso o Licita, já logado, pede um
# passe: cookie assinado, httpOnly, só para /documentacao, que vence junto
# com o login (12 h desde a entrada). O Caddy confere o passe a cada página
# (`forward_auth` em `verificar/`).

DOCS_COOKIE_NAME = "licita_docs"
DOCS_COOKIE_PATH = "/documentacao"
_DOCS_SALT = "licita.documentacao"
# Sem passe: a tela do Licita que pede o passe (e, sem login, cai no login).
DOCS_PEDIR_PASSE = "/abrir-documentacao"


def _fim_do_login(raw_refresh: str | None) -> int:
    agora = int(time.time())
    maximo = agora + env.sessao_maxima_horas * 3600
    if not raw_refresh:
        return maximo
    try:
        login_em = RefreshToken(raw_refresh).payload.get("login_em")
    except TokenError:
        return maximo
    return min(maximo, int(login_em) + env.sessao_maxima_horas * 3600) if login_em else maximo


class PasseDocumentacaoView(APIView):
    """`POST /api/auth/documentacao/` — o Licita logado pede o passe."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, *args, **kwargs) -> Response:
        ate = _fim_do_login(request.COOKIES.get(REFRESH_COOKIE_NAME))
        passe = signing.dumps({"u": request.user.pk, "ate": ate}, salt=_DOCS_SALT)
        response = Response(status=status.HTTP_204_NO_CONTENT)
        response.set_cookie(
            DOCS_COOKIE_NAME,
            passe,
            max_age=max(0, ate - int(time.time())),
            path=DOCS_COOKIE_PATH,
            httponly=True,
            secure=not settings.DEBUG,
            samesite="Lax",
        )
        return response


class VerificarDocumentacaoView(APIView):
    """`GET /api/auth/documentacao/verificar/` — o Caddy pergunta a cada
    página de /documentacao. 204 = pode entrar; 302 = vai pedir o passe."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def get(self, request: Request, *args, **kwargs) -> HttpResponse:
        try:
            dados = signing.loads(request.COOKIES.get(DOCS_COOKIE_NAME, ""), salt=_DOCS_SALT)
        except signing.BadSignature:
            return HttpResponseRedirect(DOCS_PEDIR_PASSE)
        valido = (
            isinstance(dados, dict)
            and int(dados.get("ate", 0)) > time.time()
            and User.objects.filter(pk=dados.get("u"), is_active=True).exists()
        )
        return HttpResponse(status=204) if valido else HttpResponseRedirect(DOCS_PEDIR_PASSE)
