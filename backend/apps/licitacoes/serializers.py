"""Serializers do app de licitações — dois grupos, com naturezas diferentes.

**Busca** (`OportunidadeSerializer`, `CompraDetalheSerializer` e amigos):
serializa o dict de oportunidade (`services._montar_oportunidade`) no formato
exato que o frontend já consome — ver
`frontend/src/app/contracts/licitacoes/oportunidade.contracts.ts`
(`OportunidadeResponse`). Não são `ModelSerializer`: a busca não persiste
(ver docs/DOMINIO.md), então não há model por trás — só um dict vindo da
orquestração em `services.py`.

**Oportunidades salvas** (`OportunidadeSalvaSerializer` e amigos, no fim do
arquivo): aí sim há model (`models.py`), porque salvar é o único momento em
que uma oportunidade vira registro.
"""

from __future__ import annotations

import datetime as dt

from rest_framework import serializers

from .models import (
    DocumentoFinanceiro,
    Entrega,
    EventoOportunidadeSalva,
    ItemParticipado,
    OportunidadeSalva,
    montar_texto_busca,
)


class OportunidadeSerializer(serializers.Serializer):
    numero_item = serializers.CharField(allow_null=True)
    descricao_resumida = serializers.CharField(allow_null=True)
    descricao_detalhada = serializers.CharField(allow_null=True)
    quantidade = serializers.FloatField(allow_null=True)
    unidade_medida = serializers.CharField(allow_null=True)
    valor_unitario_estimado = serializers.FloatField(allow_null=True)
    valor_total = serializers.FloatField(allow_null=True)
    tipo_beneficio = serializers.CharField(allow_null=True)
    criterio_julgamento = serializers.CharField(allow_null=True)
    situacao_item = serializers.CharField(allow_null=True)

    contratacao_uf = serializers.CharField(allow_null=True)
    contratacao_modalidade = serializers.CharField(allow_null=True)
    contratacao_situacao = serializers.CharField(allow_null=True)
    contratacao_data_publicacao = serializers.CharField(allow_null=True)
    contratacao_data_encerramento_proposta = serializers.CharField(allow_null=True)
    contratacao_orgao_nome = serializers.CharField(allow_null=True)
    contratacao_municipio = serializers.CharField(allow_null=True)
    contratacao_uasg = serializers.CharField(allow_null=True)
    contratacao_objeto = serializers.CharField(allow_null=True)

    # Identificam a compra no PNCP (cnpj do órgão + ano + sequencial) — é o
    # que o frontend usa pra agrupar os itens de um mesmo edital num card só
    # e pra chamar `CompraDetalheView` (documentos + CAPAG, sob demanda).
    contratacao_cnpj_orgao = serializers.CharField(allow_null=True)
    contratacao_ano_compra = serializers.CharField(allow_null=True)
    contratacao_sequencial_compra = serializers.CharField(allow_null=True)

    # `plataforma_id` casa com o registro em `apps/integracoes/plataformas.py`
    # (o frontend usa pra escolher o ícone do botão). Sem `allow_null` de
    # propósito: toda oportunidade é da plataforma escolhida e tem link de
    # disputa garantido — sem link não existe oportunidade (ver
    # services.buscar_oportunidades). Nulo aqui é bug, não dado.
    plataforma_id = serializers.CharField()
    link_plataforma = serializers.CharField()
    link_pncp = serializers.CharField(allow_null=True)

    # Selo CAPAG resolvido já na busca, quando o caminho da busca textual
    # trouxe os insumos junto do detalhe que filtra a plataforma (ver
    # `views._resolver_capag`). Nulo = sem nota OU insumos indisponíveis
    # neste caminho — aí o detalhe do card (`CompraDetalheSerializer`) é
    # quem tenta resolver.
    capag = serializers.SerializerMethodField()

    def get_capag(self, obj: dict) -> dict | None:
        return obj.get("capag")

    # O contrato do frontend não aceita `null` aqui — `srp` ausente vira
    # "não é SRP" (False), não "não sei".
    contratacao_srp = serializers.SerializerMethodField()

    def get_contratacao_srp(self, obj: dict) -> bool:
        return bool(obj.get("contratacao_srp"))


class DocumentoSerializer(serializers.Serializer):
    """Um arquivo do edital (aviso, anexo, termo de referência...), com link
    de download direto — ver `PncpClient.listar_arquivos`."""

    titulo = serializers.CharField(allow_null=True)
    tipo_documento = serializers.CharField(allow_null=True)
    url = serializers.CharField(allow_null=True)


class CapagSerializer(serializers.Serializer):
    """Ver `apps.capag.lookup.nota_para`."""

    nota = serializers.CharField()
    cor = serializers.CharField()


class PlataformaSerializer(serializers.Serializer):
    """A plataforma onde a compra de fato acontece, resolvida pelo
    `linkSistemaOrigem` do PNCP (ver `apps/integracoes/plataformas.py`).
    `id` nulo = plataforma que existe mas não está registrada aqui — o link
    e o nome continuam valendo."""

    id = serializers.CharField(allow_null=True)
    nome = serializers.CharField(allow_null=True)
    link = serializers.CharField()


class CompraDetalheSerializer(serializers.Serializer):
    """Resposta de `CompraDetalheView` — uma chamada por card, disparada
    quando o resultado da busca chega (ver docs/DOMINIO.md)."""

    documentos = DocumentoSerializer(many=True)
    capag = CapagSerializer(allow_null=True)
    plataforma = PlataformaSerializer(allow_null=True)


class OportunidadeSalvaSerializer(serializers.ModelSerializer):
    """Uma linha da lista de oportunidades salvas — e o snapshot inteiro
    (`itens`) que o modal de visualização usa para desenhar o mesmo card da
    busca sem ir na origem de novo. Ver
    `frontend/src/app/contracts/licitacoes/oportunidade-salva.contracts.ts`.
    """

    chave = serializers.CharField(read_only=True)
    # Calculado, nunca gravado (ver models.OportunidadeSalva).
    expirada = serializers.SerializerMethodField()
    salva_por = serializers.SerializerMethodField()
    # Float, não Decimal: o contrato do frontend é numérico (o mesmo
    # `valor_total` da busca), e DRF serializa Decimal como string.
    valor_total_estimado = serializers.FloatField(allow_null=True)

    class Meta:
        model = OportunidadeSalva
        fields = [
            "id",
            "chave",
            "cnpj_orgao",
            "ano_compra",
            "sequencial_compra",
            "objeto",
            "orgao_nome",
            "uasg",
            "uf",
            "municipio",
            "modalidade",
            "situacao",
            "data_publicacao",
            "data_encerramento_proposta",
            "valor_total_estimado",
            "plataforma_id",
            "plataforma_nome",
            "link_plataforma",
            "link_pncp",
            "capag",
            "itens",
            "expirada",
            "salva_por",
            "criada_em",
        ]

    def get_expirada(self, obj: OportunidadeSalva) -> bool:
        return obj.expirada()

    def get_salva_por(self, obj: OportunidadeSalva) -> str | None:
        return obj.salva_por_nome or None


class EncerradaSerializer(OportunidadeSalvaSerializer):
    """Uma linha de Encerradas: a salva mais o porquê e quando saiu do ciclo
    (anotados por `encerradas.encerradas`) e a cotação, se chegou a ter."""

    encerrada_em = serializers.DateField(read_only=True)
    motivo = serializers.CharField(read_only=True)
    motivo_label = serializers.SerializerMethodField()
    cotacao_id = serializers.SerializerMethodField()
    valor_cotado = serializers.SerializerMethodField()
    removida_em = serializers.DateTimeField(read_only=True)
    removida_por = serializers.SerializerMethodField()

    class Meta(OportunidadeSalvaSerializer.Meta):
        fields = OportunidadeSalvaSerializer.Meta.fields + [
            "encerrada_em",
            "motivo",
            "motivo_label",
            "cotacao_id",
            "valor_cotado",
            "removida_em",
            "removida_por",
        ]

    def get_motivo_label(self, obj: OportunidadeSalva) -> str:
        from .encerradas import MOTIVOS

        return MOTIVOS[obj.motivo]

    def _cotacao(self, obj: OportunidadeSalva):
        return getattr(obj, "cotacao", None) if obj.tem_cotacao else None

    def get_cotacao_id(self, obj: OportunidadeSalva) -> int | None:
        cotacao = self._cotacao(obj)
        return cotacao.pk if cotacao else None

    def get_valor_cotado(self, obj: OportunidadeSalva) -> float | None:
        cotacao = self._cotacao(obj)
        return float(cotacao.valor_cotado) if cotacao else None

    def get_removida_por(self, obj: OportunidadeSalva) -> str | None:
        return obj.removida_por_nome or None


class EmCotacaoSerializer(OportunidadeSalvaSerializer):
    """Uma linha do Cotador: a salva mais a cotação dela e a situação — o
    mesmo selo e as mesmas faltas do cartão do quadro (`ciclo.py`)."""

    cotacao_id = serializers.IntegerField(source="cotacao.pk", read_only=True)
    valor_cotado = serializers.SerializerMethodField()
    cotacao_atualizada_em = serializers.DateTimeField(
        source="cotacao.atualizada_em", read_only=True
    )
    pendencias = serializers.SerializerMethodField()
    selo = serializers.SerializerMethodField()

    class Meta(OportunidadeSalvaSerializer.Meta):
        fields = OportunidadeSalvaSerializer.Meta.fields + [
            "cotacao_id",
            "valor_cotado",
            "cotacao_atualizada_em",
            "pendencias",
            "selo",
        ]

    def get_valor_cotado(self, obj: OportunidadeSalva) -> float:
        return float(obj.cotacao.valor_cotado)

    def get_pendencias(self, obj: OportunidadeSalva) -> int:
        return obj.cotacao.totais().pendencias

    def get_selo(self, obj: OportunidadeSalva) -> dict:
        from .ciclo import situacao_da_cotacao

        return situacao_da_cotacao(obj)


class OportunidadeSalvaCriacaoSerializer(serializers.Serializer):
    """Payload de `POST /api/licitacoes/salvas/`: o próprio resultado da
    busca daquele edital (`itens`), mais o que o card já tinha resolvido à
    parte (`plataforma` do detalhe, selo `capag`).

    O resumo da lista (objeto, órgão, cidade, prazo, valor) é **derivado**
    aqui dos itens, não recebido pronto: o card já mostra esses números a
    partir dos mesmos dados, e derivar num lugar só evita lista e card
    discordarem.
    """

    itens = serializers.ListField(child=serializers.DictField(), allow_empty=False)
    capag = serializers.DictField(allow_null=True, required=False, default=None)
    plataforma = serializers.DictField(allow_null=True, required=False, default=None)

    def validate_itens(self, itens: list[dict]) -> list[dict]:
        faltando = [
            campo
            for campo in (
                "contratacao_cnpj_orgao",
                "contratacao_ano_compra",
                "contratacao_sequencial_compra",
            )
            if not itens[0].get(campo)
        ]
        if faltando:
            # Sem a tripla não há identidade de compra: não dá pra impedir
            # duplicata nem pra rebuscar o detalhe depois.
            raise serializers.ValidationError(
                "Oportunidade sem identificação da compra no PNCP: " + ", ".join(faltando)
            )
        return itens

    def create(self, validated_data: dict) -> OportunidadeSalva:
        itens = validated_data["itens"]
        contratacao = itens[0]
        plataforma = validated_data.get("plataforma") or {}
        objeto = contratacao.get("contratacao_objeto") or ""

        return OportunidadeSalva.objects.create(
            cnpj_orgao=contratacao["contratacao_cnpj_orgao"],
            ano_compra=contratacao["contratacao_ano_compra"],
            sequencial_compra=contratacao["contratacao_sequencial_compra"],
            objeto=objeto,
            orgao_nome=contratacao.get("contratacao_orgao_nome") or "",
            uasg=contratacao.get("contratacao_uasg") or "",
            uf=contratacao.get("contratacao_uf") or "",
            municipio=contratacao.get("contratacao_municipio") or "",
            modalidade=contratacao.get("contratacao_modalidade") or "",
            situacao=contratacao.get("contratacao_situacao") or "",
            data_publicacao=_data(contratacao.get("contratacao_data_publicacao")),
            data_encerramento_proposta=_data(
                contratacao.get("contratacao_data_encerramento_proposta")
            ),
            valor_total_estimado=_valor_total(itens),
            # A plataforma do detalhe (`linkSistemaOrigem` do PNCP) tem
            # prioridade sobre o palpite da busca — mesma regra do card.
            plataforma_id=plataforma.get("id") or contratacao.get("plataforma_id") or "",
            plataforma_nome=plataforma.get("nome") or "",
            link_plataforma=plataforma.get("link") or contratacao.get("link_plataforma") or "",
            link_pncp=contratacao.get("link_pncp") or "",
            capag=validated_data.get("capag") or contratacao.get("capag"),
            itens=itens,
            texto_busca=montar_texto_busca(objeto, itens),
            salva_por=self.context["request"].user,
        )


def _data(valor: object) -> dt.date | None:
    """As datas do PNCP chegam como texto (`AAAA-MM-DD`, ver `_so_data` no
    client do compras.gov.br). Texto irreconhecível vira `None` — melhor sem
    prazo (a oportunidade nunca expira) do que com um prazo inventado."""

    if not isinstance(valor, str):
        return None
    try:
        return dt.date.fromisoformat(valor[:10])
    except ValueError:
        return None


def _valor_total(itens: list[dict]) -> float | None:
    """Soma dos itens — `None` se algum item não tiver valor, em vez de somar
    parcial e passar por total (mesma regra do card, ver
    `valorTotalEdital` em edital-card.component.ts)."""

    valores = [item.get("valor_total") for item in itens]
    if not valores or any(valor is None for valor in valores):
        return None
    return sum(valores)


class EventoOportunidadeSalvaSerializer(serializers.ModelSerializer):
    """Uma linha do histórico (ver `models.EventoOportunidadeSalva`). O
    módulo que exibe isso ainda não existe; o endpoint existe para que o log
    seja verificável desde já."""

    autor = serializers.SerializerMethodField()
    tipo_label = serializers.CharField(source="get_tipo_display", read_only=True)

    class Meta:
        model = EventoOportunidadeSalva
        fields = ["id", "tipo", "tipo_label", "descricao", "autor", "dados", "ocorrido_em"]

    def get_autor(self, obj: EventoOportunidadeSalva) -> str | None:
        return obj.autor_nome or None


class DescartadaSerializer(OportunidadeSalvaSerializer):
    """Uma linha de Descartadas: a salva, por que e quando foi descartada
    (tirada da lista ou prazo vencido sem cotação), quem tirou, e onde ela
    estava (Oportunidade ou Cotação — com a cotação, se tinha).
    Anotada por `encerradas.descartadas`."""

    descartada_em = serializers.DateField(read_only=True)
    motivo = serializers.CharField(read_only=True)
    motivo_label = serializers.SerializerMethodField()
    estava_em = serializers.SerializerMethodField()
    cotacao_id = serializers.SerializerMethodField()
    valor_cotado = serializers.SerializerMethodField()
    removida_em = serializers.DateTimeField(read_only=True)
    removida_por = serializers.SerializerMethodField()
    # Lixeira: "Descartada manualmente por Carlinhos em 09/11/2026, na etapa
    # Aguardando julgamento. Tinha preço no item 2 (…)". Vazio nos outros motivos.
    motivo_detalhe = serializers.SerializerMethodField()

    class Meta(OportunidadeSalvaSerializer.Meta):
        fields = OportunidadeSalvaSerializer.Meta.fields + [
            "descartada_em",
            "motivo",
            "motivo_label",
            "motivo_detalhe",
            "estava_em",
            "cotacao_id",
            "valor_cotado",
            "removida_em",
            "removida_por",
        ]

    def _cotacao(self, obj: OportunidadeSalva):
        return getattr(obj, "cotacao", None) if obj.tem_cotacao else None

    def get_motivo_label(self, obj: OportunidadeSalva) -> str:
        from .encerradas import MOTIVOS_DESCARTE

        return MOTIVOS_DESCARTE[obj.motivo]

    def get_motivo_detalhe(self, obj: OportunidadeSalva) -> str:
        if obj.motivo != "descartada_manual":
            return ""
        return getattr(obj, "motivo_detalhe", "") or ""

    def get_estava_em(self, obj: OportunidadeSalva) -> str:
        return "cotacao" if obj.tem_cotacao else "oportunidade"

    def get_cotacao_id(self, obj: OportunidadeSalva) -> int | None:
        cotacao = self._cotacao(obj)
        return cotacao.pk if cotacao else None

    def get_valor_cotado(self, obj: OportunidadeSalva) -> float | None:
        cotacao = self._cotacao(obj)
        return float(cotacao.valor_cotado) if cotacao else None

    def get_removida_por(self, obj: OportunidadeSalva) -> str | None:
        return obj.removida_por_nome or None


class _LancamentoComItemSerializer(serializers.ModelSerializer):
    """Base dos lançamentos manuais da Torre: o item é escolhido pelo número,
    como está no edital ("49"), e precisa ser desta licitação."""

    item_numero = serializers.CharField(required=False, allow_blank=True, write_only=True)

    def validate_item_numero(self, valor: str) -> str:
        return valor.strip()

    def _item(self, numero: str) -> ItemParticipado | None:
        if not numero:
            return None
        oportunidade = self.context["oportunidade"]
        item = oportunidade.itens_participados.filter(numero_item=numero).first()
        if item is None:
            raise serializers.ValidationError({"item_numero": f"O item {numero} não é desta licitação."})
        return item

    def create(self, validated_data):
        numero = validated_data.pop("item_numero", "")
        validated_data["item"] = self._item(numero)
        validated_data["oportunidade"] = self.context["oportunidade"]
        return super().create(validated_data)

    def to_representation(self, instance):
        dados = super().to_representation(instance)
        dados["item_numero"] = instance.item.numero_item if instance.item_id else None
        return dados


class DocumentoFinanceiroSerializer(_LancamentoComItemSerializer):
    """Contrato, ata, empenho, ordem de fornecimento, liquidação ou pagamento.
    Lançado à mão sempre com fonte "manual"; os que vieram do PNCP ou do
    Portal da Transparência aparecem na mesma lista, só para leitura."""

    tipo_rotulo = serializers.CharField(source="get_tipo_display", read_only=True)
    fonte_rotulo = serializers.CharField(source="get_fonte_display", read_only=True)
    valor = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=0, required=False, allow_null=True)

    class Meta:
        model = DocumentoFinanceiro
        fields = [
            "id",
            "tipo",
            "tipo_rotulo",
            "numero",
            "data",
            "valor",
            "vigente_ate",
            "item_numero",
            "fonte",
            "fonte_rotulo",
            "criado_em",
        ]
        read_only_fields = ["fonte", "criado_em"]
        # A unicidade (fonte, tipo, número) vale só com número preenchido; a
        # conferência é a de `validate`, com mensagem em vez de erro de banco.
        validators: list = []
        extra_kwargs = {"numero": {"required": False}}

    def validate(self, dados):
        numero = (dados.get("numero") or "").strip()
        dados["numero"] = numero
        if numero and DocumentoFinanceiro.objects.filter(
            fonte="manual", tipo=dados["tipo"], numero=numero
        ).exists():
            raise serializers.ValidationError({"numero": "Já existe um lançamento deste tipo com este número."})
        return dados


class EntregaSerializer(_LancamentoComItemSerializer):
    class Meta:
        model = Entrega
        fields = ["id", "data", "nota_fiscal", "observacao", "item_numero", "criada_em"]
        read_only_fields = ["criada_em"]

