"""`GET /api/notificacoes/` — as últimas 40 e quantas não lidas (de quem pede).
`POST /api/notificacoes/lidas/` — `{"ids": [...]}` marca essas; sem ids, todas."""

from __future__ import annotations

from django.db.models import Exists, OuterRef
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Leitura, Notificacao

QUANTAS = 40


class NotificacoesView(APIView):
    def get(self, request):
        lidas = Leitura.objects.filter(notificacao=OuterRef("pk"), usuario=request.user)
        todas = Notificacao.objects.select_related("oportunidade").annotate(lida=Exists(lidas))
        itens = [
            {
                "id": n.pk,
                "tipo": n.tipo,
                "nivel": n.nivel,
                "titulo": n.titulo,
                "texto": n.texto,
                "oportunidade_id": n.oportunidade_id,
                "criada_em": n.criada_em,
                "lida": n.lida,
            }
            for n in todas[:QUANTAS]
        ]
        return Response({"nao_lidas": todas.filter(lida=False).count(), "itens": itens})


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
