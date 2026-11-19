"""`GET /api/notificacoes/` — o sino em duas partes (GEN-104, 19/11/2026):
`precisa` (o que pede ação dele, até 40) e `para_saber` (o resto, até 40).
`nao_lidas` conta **só** as de `precisa` (o número vermelho);
`para_saber_nao_lidas`, as outras.
`POST /api/notificacoes/lidas/` — `{"ids": [...]}` marca essas; sem ids, todas."""

from __future__ import annotations

from django.db.models import Exists, OuterRef
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import PRECISA_DE_VOCE, Leitura, Notificacao

QUANTAS = 40


def _item(n) -> dict:
    return {
        "id": n.pk,
        "tipo": n.tipo,
        "nivel": n.nivel,
        "titulo": n.titulo,
        "texto": n.texto,
        "oportunidade_id": n.oportunidade_id,
        "criada_em": n.criada_em,
        "lida": n.lida,
    }


class NotificacoesView(APIView):
    def get(self, request):
        lidas = Leitura.objects.filter(notificacao=OuterRef("pk"), usuario=request.user)
        todas = Notificacao.objects.select_related("oportunidade").annotate(lida=Exists(lidas))
        precisa = todas.filter(tipo__in=PRECISA_DE_VOCE)
        para_saber = todas.exclude(tipo__in=PRECISA_DE_VOCE)
        return Response(
            {
                "nao_lidas": precisa.filter(lida=False).count(),
                "para_saber_nao_lidas": para_saber.filter(lida=False).count(),
                "precisa": [_item(n) for n in precisa[:QUANTAS]],
                "para_saber": [_item(n) for n in para_saber[:QUANTAS]],
            }
        )


class LidasView(APIView):
    def post(self, request):
        if not request.user.is_active:
            return Response(status=403)
        ids = request.data.get("ids")
        alvo = Notificacao.objects.exclude(leituras__usuario=request.user)
        if isinstance(ids, list):
            alvo = alvo.filter(pk__in=[i for i in ids if isinstance(i, int)])
        Leitura.objects.bulk_create(
            [Leitura(notificacao=n, usuario=request.user) for n in alvo], ignore_conflicts=True
        )
        return Response({"ok": True})


class TesteTelegramView(APIView):
    """`POST /api/notificacoes/teste-telegram/` — manda uma mensagem de teste."""

    def post(self, request):
        from .telegram import chats, ligado, mandar_teste

        if not request.user.is_active:
            return Response(status=403)
        if not ligado():
            return Response({"ligado": False, "enviados": 0, "chats": 0})
        quem = getattr(request.user, "nome", "") or request.user.email
        return Response({"ligado": True, "enviados": mandar_teste(quem), "chats": len(chats())})
