"""O sino do Licita (09/11/2026): o que pede atenção, num lugar só.

Uma notificação vale para a equipe inteira; cada pessoa marca as suas como
lidas (`Leitura`). `chave` impede repetir o mesmo aviso (ex.: a mesma
convocação lida de novo na próxima ronda).
"""

from __future__ import annotations

from django.conf import settings
from django.db import models


class Notificacao(models.Model):
    class Tipo(models.TextChoices):
        CONVOCACAO = "convocacao", "Convocação"
        DESCONTO = "desconto", "Pedido de desconto"
        RECURSO = "recurso", "Recurso"
        DATA = "data", "Data alterada"
        SITUACAO = "situacao", "Compra suspensa, revogada ou anulada"
        FAVORITO = "favorito", "Fora dos favoritos"
        RESULTADO = "resultado", "Resultado saiu"
        RELATORIO = "relatorio", "Relatório completo"
        # A caixa de mensagens do fornecedor no Compras.gov.br (09/11/2026).
        MENSAGEM = "mensagem", "Mensagem do Compras.gov"

    class Nivel(models.TextChoices):
        ALERTA = "alerta", "Alerta"
        AVISO = "aviso", "Aviso"
        INFO = "info", "Informação"

    tipo = models.CharField("tipo", max_length=16, choices=Tipo.choices)
    nivel = models.CharField("nível", max_length=8, choices=Nivel.choices, default=Nivel.INFO)
    titulo = models.CharField("título", max_length=200)
    texto = models.TextField("texto", blank=True)
    oportunidade = models.ForeignKey(
        "licitacoes.OportunidadeSalva",
        verbose_name="licitação",
        related_name="notificacoes",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    chave = models.CharField("chave", max_length=200, unique=True)
    criada_em = models.DateTimeField("criada em", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "notificação"
        verbose_name_plural = "notificações"
        ordering = ["-criada_em", "-id"]

    def __str__(self) -> str:
        return self.titulo


class Leitura(models.Model):
    notificacao = models.ForeignKey(Notificacao, related_name="leituras", on_delete=models.CASCADE)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="+", on_delete=models.CASCADE)
    lida_em = models.DateTimeField("lida em", auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["notificacao", "usuario"], name="leitura_unica")]
