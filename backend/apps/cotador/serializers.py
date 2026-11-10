"""Serializers do Cotador.

O corpo de escrita é o **estado inteiro da tela**: padrões, itens e as
ofertas de cada item. Salvar substitui tudo (apaga os itens e regrava), e
não faz merge campo a campo — o modal é um editor do documento completo, e
um merge parcial deixaria para trás o item que o operador acabou de
remover.

O corpo de leitura acrescenta os **derivados** (preço final, preço de
reserva, lucro, totais). Eles não são gravados nos itens: quem recalcula a
cada tecla é o frontend, e quem confere na hora de gravar é
`formulas.py`. Vêm na resposta para que a tela abra já com os números certos
sem uma segunda volta, e para que a lista de oportunidades salvas mostre o
valor cotado sem refazer a conta.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from apps.fornecedores.models import Fornecedor
from apps.produtos.models import Fabricante, Marca, Modelo, PrecoFornecedor

from .formulas import calcular_item, totalizar
from .models import Cotacao, ItemCotacao, OfertaFornecedor

# Percentual fora deste intervalo é erro de digitação, não configuração:
# 1000% de transporte não é um cenário, é um zero a mais.
PERCENTUAL_MAXIMO = Decimal("100")


def _percentual(nome: str, *, opcional: bool = False):
    """Um campo de percentual em pontos percentuais (35 = 35%).

    `opcional` é o percentual **do item**, onde nulo significa "usa o padrão
    da cotação" (ver `formulas.Item`) — e não pode virar zero, que é uma
    decisão diferente.
    """

    return serializers.DecimalField(
        max_digits=6,
        decimal_places=2,
        min_value=Decimal("0"),
        max_value=PERCENTUAL_MAXIMO,
        label=nome,
        required=not opcional,
        allow_null=opcional,
    )


def _markup(nome: str, *, opcional: bool = False):
    """O acréscimo sobre o custo, em pontos percentuais (45 = 45%).

    Diferente dos demais percentuais, **markup não tem teto**: em item de
    baixo custo passar de 100% é rotina, e cortar em 100 seria recusar
    preço legítimo. O limite que sobra é o da coluna (`max_digits=6`), que
    devolve erro de validação em vez de estourar no banco.

    Os nomes de campo ainda dizem "margem"/"lucro" porque são os do banco e
    do contrato; o que viaja neles sempre foi o percentual sobre o custo.
    """

    return serializers.DecimalField(
        max_digits=6,
        decimal_places=2,
        min_value=Decimal("0"),
        label=nome,
        required=not opcional,
        allow_null=opcional,
    )


class OfertaSerializer(serializers.ModelSerializer):
    fornecedor = serializers.PrimaryKeyRelatedField(
        queryset=Fornecedor.objects.all(), allow_null=True, required=False
    )
    fabricante = serializers.PrimaryKeyRelatedField(
        queryset=Fabricante.objects.all(), allow_null=True, required=False
    )
    marca = serializers.PrimaryKeyRelatedField(
        queryset=Marca.objects.all(), allow_null=True, required=False
    )
    modelo = serializers.PrimaryKeyRelatedField(
        queryset=Modelo.objects.all(), allow_null=True, required=False
    )
    # Derivado — a tela mostra o custo unitário ao lado dos três campos.
    custo_unitario = serializers.DecimalField(
        max_digits=16, decimal_places=4, read_only=True
    )

    class Meta:
        model = OfertaFornecedor
        fields = [
            "id",
            "fornecedor",
            "nome",
            "fabricante",
            "fabricante_nome",
            "marca",
            "marca_nome",
            "modelo",
            "modelo_nome",
            "custo_produto",
            "frete",
            "outros",
            "escolhida",
            "custo_unitario",
        ]
        read_only_fields = ["id", "fabricante_nome", "marca_nome", "modelo_nome"]

    def validate(self, dados: dict) -> dict:
        # A hierarquia tem de fechar: marca do fabricante, modelo da marca.
        # Um nível escolhido sem o de cima é completado a partir dele.
        modelo, marca = dados.get("modelo"), dados.get("marca")
        if modelo:
            if marca and modelo.marca_id != marca.pk:
                raise serializers.ValidationError("O modelo não é dessa marca.")
            dados["marca"] = marca = modelo.marca
        if marca:
            fabricante = dados.get("fabricante")
            if fabricante and marca.fabricante_id != fabricante.pk:
                raise serializers.ValidationError("A marca não é desse fabricante.")
            dados["fabricante"] = marca.fabricante
        return dados


class ItemSerializer(serializers.ModelSerializer):
    ofertas = OfertaSerializer(many=True)

    # Nulo = "usa o padrão da cotação". Declarados aqui (e não via
    # `extra_kwargs`) porque campo declarado ignora `extra_kwargs` — o
    # `allow_null` precisa vir no próprio campo.
    margem_minima = _markup("markup mínimo", opcional=True)
    margem_maxima = _markup("markup alvo", opcional=True)
    impostos = _percentual("tributos", opcional=True)

    class Meta:
        model = ItemCotacao
        fields = [
            "id",
            "numero_item",
            "descricao",
            "unidade",
            "quantidade",
            "valor_referencia",
            "margem_minima",
            "margem_maxima",
            "impostos",
            "ofertas",
        ]
        read_only_fields = ["id"]

    def validate_ofertas(self, ofertas: list[dict]) -> list[dict]:
        if not ofertas:
            raise serializers.ValidationError(
                "Todo item precisa de pelo menos um fornecedor (ainda que sem preço)."
            )
        escolhidas = [oferta for oferta in ofertas if oferta.get("escolhida")]
        if len(escolhidas) > 1:
            raise serializers.ValidationError(
                "Só um fornecedor pode estar escolhido por item."
            )
        return ofertas


class CotacaoSerializer(serializers.ModelSerializer):
    """Leitura e escrita da cotação inteira."""

    itens = ItemSerializer(many=True)

    transporte = _percentual("transporte")
    garantia = _percentual("garantia extra")
    lucro_minimo = _markup("markup mínimo")
    lucro_maximo = _markup("markup alvo")
    impostos = _percentual("tributos")

    oportunidade_id = serializers.IntegerField(source="oportunidade.id", read_only=True)
    oportunidade_objeto = serializers.CharField(
        source="oportunidade.objeto", read_only=True, default=""
    )
    atualizada_por_nome = serializers.SerializerMethodField()
    totais = serializers.SerializerMethodField()
    itens_calculados = serializers.SerializerMethodField()

    class Meta:
        model = Cotacao
        fields = [
            "id",
            "oportunidade_id",
            "oportunidade_objeto",
            "titulo",
            "transporte",
            "garantia",
            "lucro_minimo",
            "lucro_maximo",
            "impostos",
            "itens",
            "valor_cotado",
            "preco_reserva",
            "lucro_total",
            "capital",
            "impostos_embutidos",
            "custo_produtos",
            "totais",
            "itens_calculados",
            "atualizada_por_nome",
            "criada_em",
            "atualizada_em",
        ]
        read_only_fields = [
            "id",
            "valor_cotado",
            "preco_reserva",
            "lucro_total",
            "capital",
            "impostos_embutidos",
            "custo_produtos",
            "criada_em",
            "atualizada_em",
        ]
        extra_kwargs = {"titulo": {"required": False, "allow_blank": True}}

    # O título vem do objeto do edital, que pode passar de 255 caracteres
    # (Dispensa 27/2026, 343): cortar em vez de recusar a cotação inteira.
    titulo = serializers.CharField(required=False, allow_blank=True)

    def validate_titulo(self, titulo: str) -> str:
        limite = Cotacao._meta.get_field("titulo").max_length
        titulo = titulo.strip()
        return titulo if len(titulo) <= limite else titulo[: limite - 1].rstrip() + "…"

    def validate(self, dados: dict) -> dict:
        """O piso não pode passar o alvo: com mínimo acima do máximo, o
        preço de reserva ficaria acima do preço proposto e a tela mostraria
        uma folga negativa."""

        minimo = dados.get("lucro_minimo", getattr(self.instance, "lucro_minimo", None))
        maximo = dados.get("lucro_maximo", getattr(self.instance, "lucro_maximo", None))
        if minimo is not None and maximo is not None and minimo > maximo:
            raise serializers.ValidationError(
                {"lucro_minimo": "O markup mínimo não pode ser maior que o alvo."}
            )
        return dados

    def get_atualizada_por_nome(self, cotacao: Cotacao) -> str | None:
        usuario = cotacao.atualizada_por or cotacao.criada_por
        if not usuario:
            return None
        return usuario.nome or usuario.email

    def get_totais(self, cotacao: Cotacao) -> dict:
        totais = totalizar(cotacao.para_calculo(), cotacao.padroes)
        return {
            "itens": totais.itens,
            "unidades": totais.unidades,
            "custo_produtos": totais.custo_produtos,
            "capital": totais.capital,
            "transporte": totais.transporte,
            "garantia": totais.garantia,
            "impostos": totais.impostos,
            "valor_cotado": totais.valor_cotado,
            "preco_reserva": totais.preco_reserva,
            "folga": totais.folga,
            "lucro_total": totais.lucro_total,
            "lucro_percentual": totais.lucro_percentual,
            "margem_media": totais.margem_media,
            "markup_medio": totais.markup_medio,
            "economia": totais.economia,
            "pendencias": totais.pendencias,
        }

    def get_itens_calculados(self, cotacao: Cotacao) -> list[dict]:
        """Os derivados de cada item, na mesma ordem de `itens` — é o que a
        planilha exportada imprime e o que a tela confere contra a própria
        conta."""

        padroes = cotacao.padroes
        calculados = []
        for item in cotacao.para_calculo():
            c = calcular_item(item, padroes)
            calculados.append(
                {
                    "custo_unitario": c.custo_unitario,
                    "preco_final_unitario": c.preco_final_unitario,
                    "preco_reserva_unitario": c.preco_reserva_unitario,
                    "lucro_unitario": c.lucro_unitario,
                    "imposto_unitario": c.imposto_unitario,
                    "folga_unitaria": c.folga_unitaria,
                    "preco_final_total": c.preco_final_total,
                    "lucro_total": c.lucro_total,
                    "margem_minima": c.margem_minima,
                    "margem_maxima": c.margem_maxima,
                    "incompleto": c.incompleto,
                    "economia_unitaria": c.economia_unitaria,
                }
            )
        return calculados

    # ---------- escrita ----------

    @transaction.atomic
    def create(self, validated_data: dict) -> Cotacao:
        itens = validated_data.pop("itens")
        cotacao = Cotacao.objects.create(**validated_data)
        self._gravar_itens(cotacao, itens)
        cotacao.recalcular()
        return cotacao

    @transaction.atomic
    def update(self, cotacao: Cotacao, validated_data: dict) -> Cotacao:
        itens = validated_data.pop("itens", None)
        for campo, valor in validated_data.items():
            setattr(cotacao, campo, valor)
        cotacao.save()

        if itens is not None:
            # Substituição, não merge — ver docstring do módulo. As ofertas
            # somem junto por cascade.
            cotacao.itens.all().delete()
            self._gravar_itens(cotacao, itens)

        cotacao.recalcular()
        return cotacao

    @staticmethod
    def _gravar_itens(cotacao: Cotacao, itens: list[dict]) -> None:
        for ordem, dados in enumerate(itens):
            ofertas = dados.pop("ofertas")
            item = ItemCotacao.objects.create(cotacao=cotacao, ordem=ordem, **dados)

            # Sem oferta marcada, a primeira entra na conta (é o que
            # `formulas.escolhida` faz) — gravar isso explícito deixa o
            # banco contando a mesma história que a tela.
            if not any(oferta.get("escolhida") for oferta in ofertas):
                ofertas[0]["escolhida"] = True

            OfertaFornecedor.objects.bulk_create(
                OfertaFornecedor(
                    item=item,
                    ordem=posicao,
                    fornecedor=oferta.get("fornecedor"),
                    # Nome do cadastro quando há vínculo: o snapshot não
                    # pode divergir do fornecedor escolhido só porque a tela
                    # mandou o texto antigo.
                    nome=(
                        oferta["fornecedor"].nome
                        if oferta.get("fornecedor")
                        else (oferta.get("nome") or "")
                    ),
                    fabricante=oferta.get("fabricante"),
                    fabricante_nome=oferta["fabricante"].nome if oferta.get("fabricante") else "",
                    marca=oferta.get("marca"),
                    marca_nome=oferta["marca"].nome if oferta.get("marca") else "",
                    modelo=oferta.get("modelo"),
                    modelo_nome=oferta["modelo"].nome if oferta.get("modelo") else "",
                    custo_produto=oferta.get("custo_produto") or 0,
                    frete=oferta.get("frete") or 0,
                    outros=oferta.get("outros") or 0,
                    escolhida=bool(oferta.get("escolhida")),
                )
                for posicao, oferta in enumerate(ofertas)
            )
            for oferta in ofertas:
                _aprender(cotacao, oferta)


def _aprender(cotacao: Cotacao, oferta: dict) -> None:
    """O que uma oferta ensina ao cadastro de produtos (ver
    `apps.produtos.models`): o fornecedor vende o fabricante (afinidade), e
    o custo dele para o modelo entra na tabela de preços — só quando muda,
    para salvar a cotação de novo não repetir a mesma linha."""

    fornecedor, fabricante, modelo = (
        oferta.get("fornecedor"),
        oferta.get("fabricante"),
        oferta.get("modelo"),
    )
    if fornecedor and fabricante:
        fabricante.fornecedores.add(fornecedor)
    custo = oferta.get("custo_produto") or 0
    if not (fornecedor and modelo and custo > 0):
        return
    ultimo = PrecoFornecedor.objects.filter(fornecedor=fornecedor, modelo=modelo).first()
    if ultimo and ultimo.custo == custo:
        return
    PrecoFornecedor.objects.create(
        fornecedor=fornecedor,
        modelo=modelo,
        custo=custo,
        cotacao=cotacao,
        registrado_por=cotacao.atualizada_por,
    )


class CotacaoResumoSerializer(serializers.ModelSerializer):
    """O que a lista de oportunidades salvas precisa saber sobre a cotação:
    que ela existe, quanto vale e quando mudou. Sem itens — a tabela não
    desenha item nenhum."""

    class Meta:
        model = Cotacao
        fields = ["id", "titulo", "valor_cotado", "lucro_total", "atualizada_em"]

