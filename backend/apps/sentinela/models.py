"""A Sentinela — a extensão do Chrome no computador da operação, que lê o
Compras.gov.br na sessão do próprio Carlinhos e manda para o Licita.

Aqui fica só o **sinal de vida** dela: quando falou pela última vez e em que
estado estava. O que ela lê vai para os models da Torre
(`ParticipacaoCompra`, `ItemParticipado`, em `apps/licitacoes`), por
`ingestao.py`. Plano e limites: docs/SENTINELA.md.
"""

from __future__ import annotations

from django.db import models


class Pulso(models.Model):
    """Uma notícia da Sentinela: "estou viva" ou "trouxe um dado".

    Guardamos uma linha por notícia (são poucas: uma a cada poucos minutos,
    em horário comercial) para o vigia do topo do Licita saber se ela parou.
    """

    class Estado(models.TextChoices):
        OK = "ok", "Lendo"
        SESSAO_CAIU = "sessao_caiu", "A sessão do Compras.gov caiu"
        VERIFICACAO = "verificacao", "O Compras.gov pediu verificação (captcha)"
        SEM_ABA = "sem_aba", "Nenhuma aba do Compras.gov aberta"
        ERRO = "erro", "Erro"

    recebido_em = models.DateTimeField("recebido em", auto_now_add=True, db_index=True)
    estado = models.CharField("estado", max_length=16, choices=Estado.choices, default=Estado.OK)
    detalhe = models.CharField("detalhe", max_length=255, blank=True)
    versao = models.CharField("versão da extensão", max_length=20, blank=True)
    captura = models.CharField(
        "o que trouxe",
        max_length=40,
        blank=True,
        help_text="Vazio = só sinal de vida. Senão, o tipo do dado (participacoes, meus_itens…).",
    )

    class Meta:
        verbose_name = "pulso da Sentinela"
        verbose_name_plural = "pulsos da Sentinela"
        ordering = ["-recebido_em"]

    def __str__(self) -> str:
        return f"{self.recebido_em:%d/%m %H:%M} {self.estado} {self.captura}".strip()
