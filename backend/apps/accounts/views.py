"""
Endpoints de autenticação — ver docs/ARQUITETURA.md, seção "Autenticação",
para o fluxo completo (por que o `refresh` vive num cookie `httpOnly` e não
no corpo da resposta, por que só `/api/auth/refresh/` fica sujeito a CSRF).
"""

from __future__ import annotations

import time

from django.conf import settings
from django.http import HttpResponse
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
        return response
