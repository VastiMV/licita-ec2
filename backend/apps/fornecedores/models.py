"""Cadastro de fornecedores — quem a empresa pode comprar para revender
numa licitação.

Duas decisões de produto moldam este model, e são as mesmas de
`licitacoes.OportunidadeSalva`:

**A lista é da empresa, não do usuário.** Quem cadastrou fica registrado
(`criado_por`), mas o fornecedor aparece para todos — o time cota em cima da
mesma base. Por isso não há filtro por dono em nenhuma consulta e a
unicidade do documento é global.

**Situação é dado do cadastro, não status calculado.** "Documentação
vencida" é uma escolha de quem opera (a certidão venceu, o contrato caiu),
não algo que o sistema descubra sozinho — não há data de validade de
certidão aqui para deduzir isso. O Cotador usa a situação para avisar que
um fornecedor não deveria entrar num processo novo, mas não bloqueia: a
decisão continua sendo de quem está montando a proposta.

Excluir é exclusão de verdade (não lógica, ao contrário da oportunidade
salva): não há histórico a preservar aqui, e uma cotação que já tenha usado
o fornecedor não fica órfã — ela guarda o nome como snapshot e a FK cai
para nulo (ver `apps.cotador.models.OfertaFornecedor`).
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from .documentos import formatar_documento, somente_digitos


class Categoria(models.TextChoices):
    MATERIAIS = "materiais", "Materiais"
    EQUIPAMENTOS = "equipamentos", "Equipamentos"
    SERVICOS = "servicos", "Serviços"
    LOGISTICA = "logistica", "Logística"
    TECNOLOGIA = "tecnologia", "Tecnologia"


class Tipo(models.TextChoices):
    PJ = "pj", "Pessoa jurídica"
    PF = "pf", "Pessoa física"
    MEI = "mei", "MEI"


class Situacao(models.TextChoices):
    ATIVO = "ativo", "Ativo"
    EM_ANALISE = "em_analise", "Em análise"
    INATIVO = "inativo", "Inativo"
    DOCUMENTACAO_VENCIDA = "documentacao_vencida", "Documentação vencida"


class CondicaoPagamento(models.TextChoices):
    A_VISTA = "a_vista", "À vista"
    D7 = "7_dias", "7 dias"
    D14_28 = "14_28_dias", "14/28 dias"
    D30 = "30_dias", "30 dias"
    D30_60_90 = "30_60_90_dias", "30/60/90 dias"


class FornecedorQuerySet(models.QuerySet):
    def buscar(self, termo: str) -> "FornecedorQuerySet":
        """Mesma busca da caixa única da tela: razão social, nome fantasia,
        documento, categoria e cidade num filtro só.

        O documento entra pelos dígitos (`cnpj`), então "12.345" acha
        "12345678000199" — quem digita com máscara também casa, porque o
        termo é normalizado antes de comparar.
        """

        termo = (termo or "").strip()
        if not termo:
            return self

        filtro = (
            models.Q(nome__icontains=termo)
            | models.Q(fantasia__icontains=termo)
            | models.Q(cidade__icontains=termo)
        )

        digitos = somente_digitos(termo)
        if digitos:
            filtro |= models.Q(cnpj__contains=digitos)

        # Categoria é choice: o usuário busca pelo rótulo ("Serviços"), não
        # pelo valor gravado ("servicos").
        chaves = [
            valor
            for valor, rotulo in Categoria.choices
            if termo.casefold() in rotulo.casefold()
        ]
        if chaves:
            filtro |= models.Q(categoria__in=chaves)

        return self.filter(filtro)

    def disponiveis(self) -> "FornecedorQuerySet":
        """Os que podem entrar num processo novo. "Documentação vencida" e
        "Inativo" continuam existindo no cadastro (e nas cotações antigas),
        só não são oferecidos para uma cotação nova."""

        return self.filter(situacao__in=[Situacao.ATIVO, Situacao.EM_ANALISE])


class Fornecedor(models.Model):
    nome = models.CharField("razão social", max_length=255)
    fantasia = models.CharField("nome fantasia", max_length=255, blank=True)
    tipo = models.CharField("tipo", max_length=8, choices=Tipo.choices, default=Tipo.PJ)
    # Opcional desde 10/11/2026 (GEN-19): no Cotador o fornecedor é
    # cadastrado na hora, muitas vezes sem documento. A chave é o id; o
    # documento, quando existe, continua único (ver `Meta.constraints`).
    cnpj = models.CharField(
        "CNPJ / CPF",
        max_length=14,
        blank=True,
        default="",
        help_text="Só dígitos — a máscara é da tela (ver documentos.py). Vazio = sem documento.",
    )
    inscricao_estadual = models.CharField("inscrição estadual", max_length=40, blank=True)
    categoria = models.CharField(
        "categoria", max_length=20, choices=Categoria.choices, default=Categoria.MATERIAIS
    )

    cep = models.CharField("CEP", max_length=8, blank=True)
    logradouro = models.CharField("logradouro", max_length=255, blank=True)
    numero = models.CharField("número", max_length=20, blank=True)
    complemento = models.CharField("complemento", max_length=120, blank=True)
    bairro = models.CharField("bairro", max_length=120, blank=True)
    uf = models.CharField("UF", max_length=2, blank=True)
    cidade = models.CharField("cidade", max_length=120, blank=True)

    responsavel = models.CharField("responsável", max_length=150, blank=True)
    email = models.EmailField("e-mail", blank=True)
    telefone = models.CharField("telefone", max_length=20, blank=True)
    celular = models.CharField("celular / WhatsApp", max_length=20, blank=True)

    condicao_pagamento = models.CharField(
        "condição de pagamento",
        max_length=20,
        choices=CondicaoPagamento.choices,
        default=CondicaoPagamento.D30,
    )
    prazo_entrega_dias = models.PositiveIntegerField(
        "prazo de entrega (dias)", null=True, blank=True
    )
    dados_bancarios = models.CharField("banco / agência / conta", max_length=120, blank=True)
    chave_pix = models.CharField("chave PIX", max_length=140, blank=True)

    observacoes = models.TextField("observações", blank=True)
    situacao = models.CharField(
        "situação", max_length=24, choices=Situacao.choices, default=Situacao.ATIVO
    )

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="cadastrado por",
        related_name="fornecedores_cadastrados",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    criado_por_nome = models.CharField(
        "cadastrado por (nome)",
        max_length=150,
        blank=True,
        help_text="Gravado junto com o autor: o nome continua aqui se o usuário for excluído.",
    )
    criado_em = models.DateTimeField("cadastrado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    objects = FornecedorQuerySet.as_manager()

    class Meta:
        verbose_name = "fornecedor"
        verbose_name_plural = "fornecedores"
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["cnpj"],
                condition=~models.Q(cnpj=""),
                name="fornecedor_documento_unico_quando_informado",
            )
        ]

    def __str__(self) -> str:
        return f"{self.nome} ({self.cnpj_formatado})" if self.cnpj else self.nome

    @property
    def cnpj_formatado(self) -> str:
        return formatar_documento(self.cnpj)

    @property
    def cidade_uf(self) -> str:
        """"Campinas / SP" — o que a coluna "Cidade" da tabela mostra."""

        if not self.cidade:
            return self.uf or "—"
        return f"{self.cidade} / {self.uf}" if self.uf else self.cidade

    @property
    def documentacao_vencida(self) -> bool:
        """A linha vermelha da tabela (ver a docstring do módulo)."""

        return self.situacao == Situacao.DOCUMENTACAO_VENCIDA
