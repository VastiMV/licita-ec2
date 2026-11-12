"""API da Sentinela.

A extensão usa a chave (`ChaveDaSentinela`): `pulso/`, `captura/`,
`camada/<código>/` e `ronda/`. O Licita (usuário logado) usa `estado/`.
"""

from __future__ import annotations

import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .autenticacao import ChaveDaSentinela
from .camada import numeros_da_compra
from .estado import estado_atual
from .ingestao import CapturaInvalida, receber
from .models import Pulso, Tarefa
from .ronda import consultas

logger = logging.getLogger(__name__)

TAMANHO_MAXIMO = 5_000_000  # 5 MB por captura: bem acima de uma lista real


class _DaExtensao(APIView):
    authentication_classes: list = []
    permission_classes = [ChaveDaSentinela]


class PulsoView(_DaExtensao):
    """Sinal de vida: `{"estado": "ok"|"sessao_caiu"|"sem_sessao"|"verificacao"|"sem_aba"|"erro", "detalhe", "versao"}`."""

    def post(self, request):
        estado = request.data.get("estado") or Pulso.Estado.OK
        if estado not in Pulso.Estado.values:
            return Response({"estado": "desconhecido"}, status=status.HTTP_400_BAD_REQUEST)
        Pulso.objects.create(
            estado=estado,
            detalhe=str(request.data.get("detalhe") or "")[:255],
            versao=str(request.data.get("versao") or "")[:20],
        )
        return Response({"ok": True})


class CapturaView(_DaExtensao):
    """`{"url": <o que a página chamou>, "dados": <o que ela recebeu>, "versao"}`."""

    def post(self, request):
        if int(request.META.get("CONTENT_LENGTH") or 0) > TAMANHO_MAXIMO:
            return Response({"erro": "captura grande demais"}, status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
        url = request.data.get("url")
        if not isinstance(url, str) or "dados" not in request.data:
            return Response({"erro": "faltam url e dados"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            resumo = receber(url, request.data["dados"])
        except CapturaInvalida as exc:
            logger.warning("Sentinela: captura em formato inesperado (%s): %s", url, exc)
            return Response({"erro": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        if resumo["tipo"] != "ignorado":
            Pulso.objects.create(captura=resumo["tipo"], versao=str(request.data.get("versao") or "")[:20])
        return Response(resumo)


class CamadaView(_DaExtensao):
    """Os números da camada de disputa de uma compra (código de 17 dígitos)."""

    def get(self, request, codigo: str):
        numeros = numeros_da_compra(codigo)
        if numeros is None:
            return Response({"compra": codigo, "conhecida": False, "itens": []})
        return Response({"conhecida": True, **numeros})


class TarefasView(_DaExtensao):
    """`GET tarefas/` — o que o Licita pediu (hoje: tirar favoritos)."""

    def get(self, request):
        pendentes = Tarefa.objects.filter(estado=Tarefa.Estado.PENDENTE)[:20]
        return Response([{"id": t.pk, "tipo": t.tipo, "compra": t.compra} for t in pendentes])


class TarefaView(_DaExtensao):
    """`POST tarefas/<id>/` — `{"ok": true|false, "detalhe": "..."}`."""

    def post(self, request, pk: int):
        from django.shortcuts import get_object_or_404
        from django.utils import timezone

        tarefa = get_object_or_404(Tarefa, pk=pk)
        ok = bool(request.data.get("ok"))
        if tarefa.estado == Tarefa.Estado.FEITA and not ok:
            # Duas Sentinelas ligadas (09/11/2026): a outra já tirou o
            # favorito; o "não encontrado" desta não desfaz o que foi feito.
            return Response({"ok": True, "ja_feita": True})
        tarefa.estado = Tarefa.Estado.FEITA if ok else Tarefa.Estado.ERRO
        tarefa.resultado = str(request.data.get("detalhe") or "")[:255]
        tarefa.feita_em = timezone.now()
        tarefa.save(update_fields=["estado", "resultado", "feita_em"])
        return Response({"ok": True})


class RondaView(_DaExtensao):
    """`GET ronda/` — os endereços (sem captcha) que a Sentinela consulta sozinha."""

    def get(self, request):
        return Response({"consultas": consultas()})


class EstadoView(APIView):
    """Para o botão "Sentinela" do topo do Licita (usuário logado)."""

    def get(self, request):
        return Response(estado_atual())
