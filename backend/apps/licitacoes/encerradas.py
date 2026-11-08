"""Encerradas e Descartadas — as licitações que saíram do Ciclo de
Licitação, cada uma na sua tela.

Como a etapa, a saída do ciclo é **calculada**, nunca gravada. A regra
mora aqui, num lugar só, para as duas listas, o processo (modal) e o quadro
não divergirem — e **uma licitação nunca aparece nas duas listas**.

**Encerradas** (`encerradas`) — só o que **participou** do certame e saiu:

- ``perdida`` — todos os itens da empresa desclassificados, inabilitados ou
  homologados para outro fornecedor;
- ``revogada``, ``anulada``, ``fracassada``, ``deserta`` — a situação da compra
  no Compras.gov.br.

**Descartadas** (`descartadas`) — tudo que saiu do ciclo antes de
participar, com ou sem cotação:

- ``descartada`` — a equipe tirou da lista antes do prazo vencer;
- ``prazo_oportunidade`` — o prazo venceu sem nenhuma cotação;
- ``prazo_cotacao`` — o prazo venceu com a cotação feita, sem sinal de
  participação, numa compra que a Sentinela não lê (fora do Compras.gov.br);
- ``sem_proposta`` — apareceu em "Minhas participações" sem proposta
  cadastrada quando a sessão abriu.

A regra é a mesma da Torre de Controle (`torre.avaliar`), escrita aqui como
consulta para a lista filtrar e ordenar no banco; `test_saidas.py` garante
que as duas concordam.

Pedido da operação: cotar não é participar. Encerrada é quem foi até o
certame; o resto foi descartado, por escolha ou por prazo.

Tirada da lista **depois** do prazo vencer: vale o prazo, que veio
primeiro — a remoção foi só limpeza. A remoção continua lógica: o registro
e o histórico ficam no banco (`ProcessoView` mostra o processo de qualquer
uma).
"""

from __future__ import annotations

import datetime as dt
import re

from django.db.models import (
    Case,
    CharField,
    DateField,
    DateTimeField,
    Exists,
    F,
    OuterRef,
    Q,
    Subquery,
    Value,
    When,
)
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone

from apps.cotador.models import Cotacao

from .models import EventoOportunidadeSalva, ItemParticipado, OportunidadeSalva, OportunidadeSalvaQuerySet
from .torre import (
    FASES_COMPRA_ANTES_DA_SESSAO,
    FORNECEDOR_INABILITADO,
    PLATAFORMA_COM_SENTINELA,
    PROPOSTA_DESCLASSIFICADA,
)

# Quem participou e saiu: a regra é a mesma da Torre (`torre.avaliar`), aqui
# em forma de consulta para a lista filtrar e ordenar no banco.
MOTIVOS: dict[str, str] = {
    "perdida": "Perdida",
    "revogada": "Revogada",
    "anulada": "Anulada",
    "fracassada": "Fracassada",
    "deserta": "Deserta",
}
MOTIVO_DA_SITUACAO = {"RE": "revogada", "AN": "anulada", "FR": "fracassada", "DE": "deserta"}

MOTIVOS_DESCARTE = {
    # A lixeira da Torre: vale sobre qualquer outra regra (ver lixeira.py).
    "descartada_manual": "Descartada manualmente",
    "descartada": "Tirada da lista",
    "prazo_oportunidade": "Prazo venceu sem cotação",
    "prazo_cotacao": "Prazo venceu com cotação",
    "sem_proposta": "Sem proposta cadastrada",
}

ITEM_PERDIDO = Q(vencedor_e_a_empresa=False) | Q(
    situacao_proposta__in=[*PROPOSTA_DESCLASSIFICADA, FORNECEDOR_INABILITADO]
)
COMPRA_ENCERRADA = Q(participacao__situacao_compra__in=list(MOTIVO_DA_SITUACAO))
# A Sentinela viu a compra nas participações depois da sessão, sem ainda ter
# lido os itens: fica no quadro esperando (mesma regra de `torre.avaliar`).
ESPERA_OS_ITENS = Q(participacao__isnull=False, participacao__proposta_cadastrada__isnull=True) & ~Q(
    participacao__fase_compra__in=FASES_COMPRA_ANTES_DA_SESSAO
)
PARTICIPOU = (
    Q(tem_itens=True) | Q(participacao__proposta_cadastrada=True) | COMPRA_ENCERRADA | ESPERA_OS_ITENS
)


def _sem_proposta(hoje: dt.date) -> Q:
    """Participou sem proposta cadastrada: a Sentinela leu
    "Minhas participações" e não havia proposta quando a sessão abriu."""

    return (
        Q(tem_itens=False, participacao__proposta_cadastrada=False)
        & (
            ~Q(participacao__fase_compra__in=FASES_COMPRA_ANTES_DA_SESSAO)
            | Q(data_encerramento_proposta__lt=hoje)
        )
        & ~COMPRA_ENCERRADA
    )


def _venceu_antes(hoje: dt.date) -> Q:
    """O prazo venceu antes de (ou sem) a remoção: saiu do ciclo pelo prazo.

    Não sai pelo prazo quem tem sinal de participação: fatos da Torre (itens,
    proposta cadastrada), proposta gerada no fluxo antigo, ou cotação feita
    numa compra do Compras.gov.br — essa espera a Sentinela confirmar."""

    prazo = "data_encerramento_proposta"
    espera_a_sentinela = Q(tem_cotacao=True, plataforma_id=PLATAFORMA_COM_SENTINELA)
    return (
        Q(**{f"{prazo}__lt": hoje}, proposta__isnull=True)
        & ~PARTICIPOU
        & ~espera_a_sentinela
        & ~_sem_proposta(hoje)
        & (Q(removida_em__isnull=True) | Q(**{f"{prazo}__lt": TruncDate("removida_em")}))
    )


def _com_fatos(lista: OportunidadeSalvaQuerySet) -> OportunidadeSalvaQuerySet:
    itens = ItemParticipado.objects.filter(oportunidade=OuterRef("pk"))
    return lista.annotate(
        tem_cotacao=Exists(Cotacao.objects.filter(oportunidade=OuterRef("pk"))),
        tem_itens=Exists(itens),
        tem_item_vivo=Exists(itens.exclude(ITEM_PERDIDO)),
    )


def encerradas(hoje: dt.date | None = None) -> OportunidadeSalvaQuerySet:
    """As encerradas — quem participou do certame e saiu —, anotadas com
    ``encerrada_em``, ``motivo`` e ``tem_cotacao``: compra revogada,
    anulada, fracassada ou deserta, ou todos os itens da empresa perdidos."""

    perdida = Q(tem_itens=True, tem_item_vivo=False)
    ultima_leitura_de_item = Subquery(
        ItemParticipado.objects.filter(oportunidade=OuterRef("pk"))
        .order_by("-atualizado_em")
        .values("atualizado_em")[:1],
        output_field=DateTimeField(),
    )
    return (
        _com_fatos(OportunidadeSalva.objects.ativas())
        .filter(COMPRA_ENCERRADA | perdida)
        .annotate(
            motivo=Case(
                *(
                    When(participacao__situacao_compra=situacao, then=Value(motivo))
                    for situacao, motivo in MOTIVO_DA_SITUACAO.items()
                ),
                default=Value("perdida"),
                output_field=CharField(),
            ),
            encerrada_em=Case(
                When(COMPRA_ENCERRADA, then=TruncDate("participacao__atualizada_em")),
                default=Coalesce(TruncDate(ultima_leitura_de_item), F("data_encerramento_proposta")),
                output_field=DateField(),
            ),
        )
    )


def descartadas(hoje: dt.date | None = None) -> OportunidadeSalvaQuerySet:
    """As descartadas — tiradas da lista antes do prazo, com o prazo vencido
    sem sinal de participação, ou que participaram sem proposta cadastrada —,
    anotadas com ``motivo``, ``descartada_em`` (o que veio primeiro: o dia da
    remoção ou o prazo) e ``tem_cotacao`` (onde estava: Oportunidade ou
    Cotação)."""

    hoje = hoje or timezone.localdate()
    venceu = _venceu_antes(hoje)
    sem_proposta = _sem_proposta(hoje) & Q(removida_em__isnull=True)
    tirada_antes = Q(removida_em__isnull=False) & ~venceu
    # Lixeira: descartada (removida) depois do último "voltou para a Torre".
    descartes = EventoOportunidadeSalva.objects.filter(
        oportunidade=OuterRef("pk"), tipo=EventoOportunidadeSalva.Tipo.DESCARTADA
    ).order_by("-ocorrido_em")
    manual = Q(removida_em__isnull=False, tem_descarte_manual=True)
    return (
        _com_fatos(OportunidadeSalva.objects.all())
        .annotate(
            tem_descarte_manual=Exists(descartes),
            motivo_detalhe=Subquery(descartes.values("descricao")[:1]),
        )
        .filter(tirada_antes | venceu | sem_proposta | manual)
        .annotate(
            motivo=Case(
                When(manual, then=Value("descartada_manual")),
                When(sem_proposta, then=Value("sem_proposta")),
                When(venceu & Q(tem_cotacao=True), then=Value("prazo_cotacao")),
                When(venceu, then=Value("prazo_oportunidade")),
                default=Value("descartada"),
                output_field=CharField(),
            ),
            descartada_em=Case(
                When(manual, then=TruncDate("removida_em")),
                When(sem_proposta, then=TruncDate("participacao__atualizada_em")),
                When(venceu, then=F("data_encerramento_proposta")),
                default=TruncDate("removida_em"),
                output_field=DateField(),
            ),
        )
    )


# ---------- o processo (modal) ----------

VALOR_NA_DESCRICAO = re.compile(r"R\$ ([\d.]+)")


def _valor_do_evento(evento: EventoOportunidadeSalva) -> float | None:
    """Eventos novos guardam o valor em `dados`; os antigos só o tinham no
    texto ("— valor cotado R$ 2065.56.")."""

    if "valor_cotado" in evento.dados:
        return float(evento.dados["valor_cotado"])
    achado = VALOR_NA_DESCRICAO.search(evento.descricao)
    return float(achado.group(1).rstrip(".")) if achado else None


def _cotacao_criada(evento: EventoOportunidadeSalva) -> bool:
    if "criada" in evento.dados:
        return bool(evento.dados["criada"])
    return evento.descricao.startswith("Cotação criada")


def _brl(valor: float) -> str:
    inteiro, centavos = f"{valor:,.2f}".split(".")
    return f"R$ {inteiro.replace(',', '.')},{centavos}"


def _dia(momento: dt.datetime | dt.date) -> str:
    if isinstance(momento, dt.datetime):
        momento = timezone.localtime(momento)
    return f"{momento:%d/%m}"


def montar_processo(salva: OportunidadeSalva, hoje: dt.date | None = None) -> dict:
    """A história de uma salva no formato do modal do processo: cada evento
    com a etapa em que aconteceu e o valor (quando houver), a etapa atual e,
    se encerrou, o desfecho com o "por que parou aqui" já escrito."""

    hoje = hoje or timezone.localdate()
    Tipo = EventoOportunidadeSalva.Tipo
    eventos: list[dict] = []
    etapa = "oportunidade"
    for evento in salva.eventos.order_by("ocorrido_em", "id"):
        item = {
            "id": evento.pk,
            "autor": evento.autor_nome or None,
            "data": evento.ocorrido_em,
            "valor": None,
        }
        if evento.tipo == Tipo.PROPOSTA_GERADA:
            etapa = "cotacao"
            criada = _cotacao_criada(evento)
            item |= {
                "tipo": "cotacao_criada" if criada else "cotacao_atualizada",
                "texto": "Cotação criada" if criada else "Cotação atualizada",
                "valor": _valor_do_evento(evento),
            }
        elif evento.tipo == Tipo.PROPOSTA:
            etapa = "proposta"
            item |= {
                "tipo": "proposta_gerada",
                "texto": "Proposta gerada",
                "valor": evento.dados.get("valor"),
            }
        elif evento.tipo == Tipo.SALVA:
            item |= {"tipo": "oportunidade_salva", "texto": "Oportunidade salva"}
        elif evento.tipo == Tipo.PRAZO_VENCIDO:
            sem = "sem proposta" if etapa == "cotacao" else "sem cotação"
            item |= {"tipo": "prazo_encerrado", "texto": f"Prazo de proposta encerrado {sem}"}
        elif evento.tipo == Tipo.REMOVIDA:
            item |= {"tipo": "removida", "texto": "Removida da lista"}
        elif evento.tipo in (Tipo.DESCARTADA, Tipo.VOLTOU):
            # O texto completo (quem, quando, etapa, preço) é a própria descrição.
            item |= {"tipo": evento.tipo, "texto": evento.descricao}
        else:
            item |= {"tipo": evento.tipo, "texto": evento.get_tipo_display()}
        eventos.append({**item, "etapa": etapa})

    # Saiu do ciclo por uma das duas listas (nunca pelas duas): o motivo
    # anotado escolhe o texto do desfecho.
    encerrada = (
        encerradas(hoje).filter(pk=salva.pk).first()
        or descartadas(hoje).filter(pk=salva.pk).first()
    )
    return {
        "id": salva.pk,
        "etapa": etapa,
        "desfecho": _desfecho(encerrada, eventos) if encerrada else None,
        "eventos": eventos,
    }


def _desfecho(salva, eventos: list[dict]) -> dict:
    if salva.motivo == "descartada_manual":
        por = salva.removida_por_nome or "Alguém"
        return {
            "tipo": "descartada_manual",
            "data": salva.removida_em,
            "por": por,
            "porque": salva.motivo_detalhe or f"{por} descartou pela lixeira da Torre.",
        }
    if salva.motivo == "sem_proposta":
        porque = (
            "A sessão pública abriu e a empresa estava sem proposta cadastrada no Compras.gov.br."
        )
        return {"tipo": "sem_proposta", "data": salva.descartada_em, "por": None, "porque": porque}
    if salva.motivo == "perdida":
        porque = (
            "A empresa perdeu todos os itens em que tinha proposta: desclassificada, "
            "inabilitada ou homologada para outro fornecedor."
        )
        return {"tipo": "perdida", "data": salva.encerrada_em, "por": None, "porque": porque}
    if salva.motivo in MOTIVO_DA_SITUACAO.values():
        porque = f"O órgão marcou a compra como {MOTIVOS[salva.motivo].lower()} no Compras.gov.br."
        return {"tipo": salva.motivo, "data": salva.encerrada_em, "por": None, "porque": porque}

    cotacoes = [e for e in eventos if e["tipo"].startswith("cotacao_")]
    salvo = next((e for e in eventos if e["tipo"] == "oportunidade_salva"), None)
    prazo = salva.data_encerramento_proposta

    if salva.motivo == "descartada":
        por = salva.removida_por_nome or "Alguém"
        quando = timezone.localtime(salva.removida_em)
        onde = "em Cotação" if cotacoes else "ainda em Oportunidade"
        resto = (
            f"A cotação tinha {_brl(cotacoes[-1]['valor'] or 0)}."
            if cotacoes
            else "Nenhuma cotação foi feita."
        )
        porque = f"{por} tirou o processo da lista em {quando:%d/%m}, às {quando:%H:%M}, {onde}. {resto}"
        return {"tipo": "descartada", "data": salva.removida_em, "por": por, "porque": porque}

    if salva.motivo == "prazo_cotacao":
        ultima = cotacoes[-1] if cotacoes else None
        detalhe = (
            f" ({_brl(ultima['valor'] or 0)}, última edição em {_dia(ultima['data'])}"
            f"{' por ' + ultima['autor'] if ultima['autor'] else ''})"
            if ultima
            else ""
        )
        porque = (
            f"A cotação estava pronta{detalhe}, mas nenhuma proposta foi registrada "
            f"até o prazo de {prazo:%d/%m/%Y}."
        )
        return {"tipo": "prazo_cotacao", "data": prazo, "por": None, "porque": porque}

    if salvo:
        dias = (prazo - timezone.localtime(salvo["data"]).date()).days
        quem = f" por {salvo['autor']}" if salvo["autor"] else ""
        porque = (
            f"Salva{quem} em {_dia(salvo['data'])}, mas nenhuma cotação foi criada nos "
            f"{dias} dia{'s' if dias != 1 else ''} até o prazo da proposta ({prazo:%d/%m/%Y})."
        )
    else:
        porque = f"Nenhuma cotação foi criada até o prazo da proposta ({prazo:%d/%m/%Y})."
    return {"tipo": "prazo_oportunidade", "data": prazo, "por": None, "porque": porque}
