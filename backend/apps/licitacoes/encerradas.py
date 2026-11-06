"""Encerradas — as licitações que saíram do Ciclo de Licitação.

Como a etapa, o encerramento é **calculado**, nunca gravado: uma salva está
encerrada quando o prazo de proposta venceu antes de ela virar proposta. O
motivo e a data saem da mesma regra, num lugar só, para a lista e o quadro
não divergirem.

Motivos de hoje (perdida na disputa e falha no empenho entram quando essas
etapas existirem):

- ``prazo_oportunidade`` — o prazo venceu sem a equipe ter cotado;
- ``prazo_cotacao`` — o prazo venceu com a cotação feita, sem proposta.

**Descartada não é encerrada.** Quem a equipe tirou da lista antes do prazo
vencer sai de Encerradas e vai para a tela Descartadas (`descartadas`) — para quem opera,
encerrado é o que não foi cotado a tempo ou o que seguiu o ciclo até o fim,
e o descarte é só "não me interessa". A remoção continua lógica: o registro
e o histórico ficam no banco (`ProcessoView` ainda mostra o processo).

Quem foi descartada **depois** do prazo vencer encerrou pelo prazo: a
remoção foi só limpeza da lista, e ela aparece aqui com o motivo do prazo.
"""

from __future__ import annotations

import datetime as dt
import re

from django.db.models import Case, CharField, Exists, F, OuterRef, Q, Value, When
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.cotador.models import Cotacao

from .models import EventoOportunidadeSalva, OportunidadeSalva, OportunidadeSalvaQuerySet

MOTIVOS = {
    "prazo_oportunidade": "Prazo perdido sem cotação",
    "prazo_cotacao": "Prazo perdido na cotação",
}


def _venceu_antes(hoje: dt.date) -> Q:
    """O prazo venceu antes de (ou sem) a remoção: encerrou pelo prazo.
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
    """As encerradas, anotadas com ``encerrada_em``, ``motivo`` e
    ``tem_cotacao``. Descartadas antes do prazo ficam de fora (ver a
    docstring do módulo e `descartadas`)."""

    hoje = hoje or timezone.localdate()
    return _com_cotacao(OportunidadeSalva.objects.filter(_venceu_antes(hoje))).annotate(
        encerrada_em=F("data_encerramento_proposta"),
        motivo=Case(
            When(tem_cotacao=True, then=Value("prazo_cotacao")),
            default=Value("prazo_oportunidade"),
            output_field=CharField(),
        ),
    )


def descartadas(hoje: dt.date | None = None) -> OportunidadeSalvaQuerySet:
    """As que a equipe tirou da lista **antes** do prazo vencer — o que saiu
    de Encerradas e ganhou tela própria. Anotadas com ``descartada_em`` (o
    dia da remoção) e ``tem_cotacao`` (onde estava: Oportunidade ou
    Cotação). Removida depois do prazo é Encerrada, não Descartada: as duas
    listas nunca mostram a mesma licitação."""

    hoje = hoje or timezone.localdate()
    return _com_cotacao(
        OportunidadeSalva.objects.filter(removida_em__isnull=False).exclude(
            _venceu_antes(hoje)
        )
    ).annotate(descartada_em=TruncDate("removida_em"))


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

    encerrada = encerradas(hoje).filter(pk=salva.pk).first()
    if encerrada is None and salva.removida_em:
        # Descartada não está em Encerradas, mas a história dela continua
        # contando quem tirou da lista e quando.
        salva.motivo = "descartada"
        encerrada = salva
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
