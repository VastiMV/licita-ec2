"""Encerradas e Descartadas — as licitações que saíram do Ciclo de
Licitação, cada uma na sua tela.

Como a etapa, a saída do ciclo é **calculada**, nunca gravada. A regra
mora aqui, num lugar só, para as duas listas, o processo (modal) e o quadro
não divergirem — e **uma licitação nunca aparece nas duas listas**.

**Encerradas** (`encerradas`) — só o que **participou** do certame:
perdida na disputa, falha no empenho, concluída. Essas etapas ainda não
existem no sistema, então hoje a lista é vazia de propósito.

**Descartadas** (`descartadas`) — tudo que saiu do ciclo antes de
participar, com ou sem cotação:

- ``descartada`` — a equipe tirou da lista antes do prazo vencer;
- ``prazo_oportunidade`` — o prazo venceu sem nenhuma cotação;
- ``prazo_cotacao`` — o prazo venceu com a cotação feita, sem proposta.

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

from django.db.models import Case, CharField, DateField, Exists, F, OuterRef, Q, Value, When
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.cotador.models import Cotacao

from .models import EventoOportunidadeSalva, OportunidadeSalva, OportunidadeSalvaQuerySet

# Os motivos de Encerradas chegam com as etapas Disputa e Empenho.
MOTIVOS: dict[str, str] = {}

MOTIVOS_DESCARTE = {
    "descartada": "Tirada da lista",
    "prazo_oportunidade": "Prazo venceu sem cotação",
    "prazo_cotacao": "Prazo venceu com cotação",
}


def _venceu_antes(hoje: dt.date) -> Q:
    """O prazo venceu antes de (ou sem) a remoção: saiu do ciclo pelo prazo.
    Com proposta gerada, o prazo vencer é o caminho normal, não perda."""

    prazo = "data_encerramento_proposta"
    return Q(**{f"{prazo}__lt": hoje}, proposta__isnull=True) & (
        Q(removida_em__isnull=True) | Q(**{f"{prazo}__lt": TruncDate("removida_em")})
    )


def _com_cotacao(lista: OportunidadeSalvaQuerySet) -> OportunidadeSalvaQuerySet:
    return lista.annotate(
        tem_cotacao=Exists(Cotacao.objects.filter(oportunidade=OuterRef("pk"))),
    )


def encerradas(hoje: dt.date | None = None) -> OportunidadeSalvaQuerySet:
    """As encerradas — quem participou do certame —, anotadas com
    ``encerrada_em``, ``motivo`` e ``tem_cotacao``. Vazia até as etapas
    Disputa e Empenho existirem (ver a docstring do módulo); a forma fica
    pronta para a tela e o processo não mudarem quando elas chegarem."""

    return _com_cotacao(OportunidadeSalva.objects.none()).annotate(
        encerrada_em=F("data_encerramento_proposta"),
        motivo=Value("", output_field=CharField()),
    )


def descartadas(hoje: dt.date | None = None) -> OportunidadeSalvaQuerySet:
    """As descartadas — tiradas da lista antes do prazo ou com o prazo
    vencido, com ou sem cotação —, anotadas com ``motivo``,
    ``descartada_em`` (o que veio primeiro: o dia da remoção ou o prazo) e
    ``tem_cotacao`` (onde estava: Oportunidade ou Cotação)."""

    hoje = hoje or timezone.localdate()
    venceu = _venceu_antes(hoje)
    tirada_antes = Q(removida_em__isnull=False) & ~venceu
    return (
        _com_cotacao(OportunidadeSalva.objects.all())
        .filter(tirada_antes | venceu)
        .annotate(
            motivo=Case(
                When(venceu & Q(tem_cotacao=True), then=Value("prazo_cotacao")),
                When(venceu, then=Value("prazo_oportunidade")),
                default=Value("descartada"),
                output_field=CharField(),
            ),
            descartada_em=Case(
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
