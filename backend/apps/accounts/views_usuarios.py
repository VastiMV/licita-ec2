"""Endpoints da tela de Usuários (Configurações → Usuários).

Mesmo contrato de tabela de `apps/fornecedores/views.py` (`busca`,
`ordering`, `page`, `page_size`), porque a tela é a mesma `DataTable`.
"""

from __future__ import annotations

from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import User
from .permissions import EhSuperusuario
from .serializers import PerfilSerializer, UsuarioSerializer


class UsuariosPaginacao(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


ORDENACOES = {
    "nome": "nome",
    "email": "email",
    "is_superuser": "is_superuser",
    "criado_em": "criado_em",
}
ORDENACAO_PADRAO = "nome"


def _ordenacao(pedida: str | None) -> str:
    pedida = (pedida or "").strip()
    campo = ORDENACOES.get(pedida.lstrip("-"))
    if not campo:
        return ORDENACAO_PADRAO
    return f"-{campo}" if pedida.startswith("-") else campo


class UsuariosView(APIView):
    """`GET/POST /api/usuarios/`."""

    permission_classes = [EhSuperusuario]

    def get(self, request: Request) -> Response:
        usuarios = User.objects.all()
        termo = request.query_params.get("busca", "").strip()
        if termo:
            usuarios = usuarios.filter(Q(nome__icontains=termo) | Q(email__icontains=termo))
        usuarios = usuarios.order_by(_ordenacao(request.query_params.get("ordering")), "email")

        paginacao = UsuariosPaginacao()
        pagina = paginacao.paginate_queryset(usuarios, request, view=self)
        return paginacao.get_paginated_response(UsuarioSerializer(pagina, many=True).data)

    def post(self, request: Request) -> Response:
        serializer = UsuarioSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=201)


class UsuarioView(APIView):
    """`GET/PUT/DELETE /api/usuarios/<id>/`."""

    permission_classes = [EhSuperusuario]

    def get(self, request: Request, pk: int) -> Response:
        return Response(UsuarioSerializer(get_object_or_404(User, pk=pk)).data)

    def put(self, request: Request, pk: int) -> Response:
        usuario = get_object_or_404(User, pk=pk)
        serializer = UsuarioSerializer(usuario, data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request: Request, pk: int) -> Response:
        usuario = get_object_or_404(User, pk=pk)
        if usuario.pk == request.user.pk:
            return Response({"detail": "Você não pode excluir o seu próprio usuário."}, status=400)
        # Exclusão de verdade. O histórico não depende do usuário: cada
        # registro guarda o nome de quem fez no momento em que fez (os campos
        # `*_nome` ao lado de cada FK de autor), e a FK cai para nulo.
        usuario.delete()
        return Response(status=204)


class PerfilView(APIView):
    """`GET/PUT /api/usuarios/eu/` — o "Editar perfil" do menu de conta.

    Qualquer usuário logado, sobre si mesmo. Nome, e-mail e senha; o super
    usuário vem na resposta mas não muda por aqui (`PerfilSerializer`).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        return Response(PerfilSerializer(request.user).data)

    def put(self, request: Request) -> Response:
        serializer = PerfilSerializer(request.user, data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class FotoView(APIView):
    """`PUT /api/usuarios/eu/foto/` `{"foto": "data:image/jpeg;base64,…"}` —
    troca a própria foto. `DELETE` tira (volta a inicial)."""

    permission_classes = [IsAuthenticated]

    def put(self, request: Request) -> Response:
        from .serializers import FotoSerializer

        serializer = FotoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request.user.foto = serializer.validated_data["foto"]
        request.user.save(update_fields=["foto"])
        return Response(PerfilSerializer(request.user).data)

    def delete(self, request: Request) -> Response:
        request.user.foto = ""
        request.user.save(update_fields=["foto"])
        return Response(PerfilSerializer(request.user).data)
