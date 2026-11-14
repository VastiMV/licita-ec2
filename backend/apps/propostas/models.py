"""Propostas — a etapa depois do Cotador.

O botão "Gerar proposta" do Cotador cria o registro, e é ele que move a
licitação de etapa (a etapa é calculada, ver `apps.licitacoes.torre`): sai
do Cotador e aparece em Propostas (PDF).

A tela de Propostas é **o lugar de tudo o que sobe na plataforma**: a
proposta comercial (gerada em Word a partir do modelo do cliente, ver
`documento.py`), os documentos de habilitação da empresa escolhida (que
moram em `apps.documentos` e aqui só são conferidos) e os arquivos desta
licitação — declarações, catálogos, a proposta assinada (`ArquivoProposta`).

Uma por oportunidade, como a cotação. O valor é gravado no momento de gerar:
mexer na cotação depois não muda o que foi proposto.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.tenants.models import tenant_campo


class Proposta(models.Model):
    oportunidade = models.OneToOneField(
        "licitacoes.OportunidadeSalva",
        verbose_name="oportunidade salva",
        related_name="proposta",
        on_delete=models.CASCADE,
    )
    valor = models.DecimalField(
        "valor proposto",
        max_digits=16,
        decimal_places=2,
        help_text="O valor cotado no momento de gerar.",
    )
    empresa = models.ForeignKey(
        "empresas.Empresa",
        verbose_name="empresa",
        related_name="propostas",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        help_text="O CNPJ com que se disputa. Nulo até escolher (com uma empresa só, é ela).",
    )
    validade_dias = models.PositiveIntegerField(
        "validade da proposta (dias)",
        default=60,
        help_text="60 é o mínimo que a maioria dos editais exige.",
    )
    gerada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="gerada por",
        related_name="propostas_geradas",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    gerada_por_nome = models.CharField("gerada por (nome)", max_length=150, blank=True)
    gerada_em = models.DateTimeField("gerada em", auto_now_add=True)

    class Meta:
        verbose_name = "proposta"
        verbose_name_plural = "propostas"

    def __str__(self) -> str:
        return f"Proposta de {self.oportunidade}"


class ModeloProposta(models.Model):
    """O Word da proposta comercial do cliente, com os campos marcados
    (`{{ empresa.nome }}`, a tabela dos itens…). Um por tenant: enviar outro
    substitui. Sem modelo enviado vale o padrão do sistema
    (`modelo_padrao.docx`)."""

    tenant = models.OneToOneField(
        "tenants.Tenant",
        verbose_name="tenant",
        related_name="modelo_proposta",
        on_delete=models.PROTECT,
    )
    arquivo = models.CharField("arquivo (chave no armazenamento)", max_length=500)
    nome_original = models.CharField("nome original", max_length=255)
    enviado_por_nome = models.CharField("enviado por", max_length=150, blank=True)
    enviado_em = models.DateTimeField("enviado em", auto_now=True)

    class Meta:
        verbose_name = "modelo de proposta"
        verbose_name_plural = "modelos de proposta"


class ArquivoProposta(models.Model):
    """Um arquivo desta licitação que sobe junto com a proposta: a proposta
    comercial gerada, a assinada, declarações, catálogos. Sem lista fixa e
    sem validade — o que é fixo e vence é documento da empresa."""

    class Origem(models.TextChoices):
        GERADO = "gerado", "Gerado pelo sistema"
        SUBIDO = "subido", "Enviado pela equipe"

    tenant = tenant_campo("arquivos_proposta")
    proposta = models.ForeignKey(
        Proposta, verbose_name="proposta", related_name="arquivos", on_delete=models.CASCADE
    )
    origem = models.CharField("origem", max_length=8, choices=Origem.choices)
    arquivo = models.CharField("arquivo (chave no armazenamento)", max_length=500)
    nome_original = models.CharField("nome", max_length=255)
    tamanho = models.PositiveBigIntegerField("tamanho (bytes)", default=0)
    content_type = models.CharField("tipo", max_length=120, blank=True)
    enviado_por_nome = models.CharField("enviado por", max_length=150, blank=True)
    enviado_em = models.DateTimeField("enviado em", auto_now_add=True)

    class Meta:
        verbose_name = "arquivo da proposta"
        verbose_name_plural = "arquivos da proposta"
        ordering = ["origem", "enviado_em", "id"]

    def __str__(self) -> str:
        return self.nome_original
