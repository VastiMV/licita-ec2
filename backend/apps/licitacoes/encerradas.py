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
from .torre import avaliar

# A regra mora na Torre (`torre.avaliar`), num lugar só (09/11/2026): antes
# ela estava escrita duas vezes (lá e aqui, como consulta), e as duas
# divergiam — o menu dizia 3 descartadas e a lista mostrava 4.
MOTIVOS: dict[str, str] = {
    "perdida": "Perdida",
    "acompanhando": "Acompanhando o resultado",
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


def _com_prefetch(lista):
    return lista.select_related("cotacao", "participacao", "proposta").prefetch_related(
        "itens_participados__propostas", "documentos_financeiros", "entregas"
    )


def classificar(hoje: dt.date | None = None) -> dict[int, tuple[str, str, dt.date | None]]:
    """Para onde saiu cada licitação que não está na Torre:
    `{id: ("encerradas" | "descartadas", chave do motivo, data)}`.

    - **Ativas**: a regra da Torre (`torre.avaliar`).
    - **Removidas**: pela lixeira (`descartada_manual`), ou tiradas da lista
      (`descartada`) — exceto se o prazo venceu antes da remoção: aí vale o
      prazo, que veio primeiro (a remoção foi só limpeza).
    """

    hoje = hoje or timezone.localdate()
    saidas: dict[int, tuple[str, str, dt.date | None]] = {}
    for salva in _com_prefetch(OportunidadeSalva.objects.ativas()):
        _, saida = avaliar(salva, hoje)
        if saida:
            saidas[salva.pk] = (saida.para, saida.chave, saida.data)

    manuais = set(
        EventoOportunidadeSalva.objects.filter(tipo=EventoOportunidadeSalva.Tipo.DESCARTADA).values_list(
            "oportunidade_id", flat=True
        )
    )
    removidas = OportunidadeSalva.objects.filter(removida_em__isnull=False).annotate(
        tem_cotacao=Exists(Cotacao.objects.filter(oportunidade=OuterRef("pk"))),
        tem_itens=Exists(ItemParticipado.objects.filter(oportunidade=OuterRef("pk"))),
    )
    for salva in removidas:
        removida = timezone.localdate(salva.removida_em)
        prazo = salva.data_encerramento_proposta
        if salva.pk in manuais:
            saidas[salva.pk] = ("descartadas", "descartada_manual", removida)
        elif prazo and prazo < removida and not salva.tem_itens:
            chave = "prazo_cotacao" if salva.tem_cotacao else "prazo_oportunidade"
            saidas[salva.pk] = ("descartadas", chave, prazo)
        else:
            saidas[salva.pk] = ("descartadas", "descartada", removida)
    return saidas


def contar(hoje: dt.date | None = None) -> dict[str, int]:
    """Os números do menu — os mesmos das listas."""

    total = {"encerradas": 0, "descartadas": 0}
    for para, _, _ in classificar(hoje).values():
        total[para] += 1
    return total


def _lista(para: str, campo_data: str, hoje: dt.date | None) -> OportunidadeSalvaQuerySet:
    saidas = {pk: v for pk, v in classificar(hoje).items() if v[0] == para}
    if not saidas:
        return OportunidadeSalva.objects.none().annotate(
            motivo=Value("", output_field=CharField()),
            **{campo_data: Value(None, output_field=DateField())},
            tem_cotacao=Value(False),
        )
    return (
        OportunidadeSalva.objects.filter(pk__in=saidas)
        .annotate(
            motivo=Case(
                *(When(pk=pk, then=Value(chave)) for pk, (_, chave, _) in saidas.items()),
                output_field=CharField(),
            ),
            **{
                campo_data: Case(
                    *(When(pk=pk, then=Value(data)) for pk, (_, _, data) in saidas.items()),
                    output_field=DateField(),
                )
            },
            tem_cotacao=Exists(Cotacao.objects.filter(oportunidade=OuterRef("pk"))),
        )
    )


def encerradas(hoje: dt.date | None = None) -> OportunidadeSalvaQuerySet:
    """As encerradas — quem participou do certame e saiu, e as que ele só
    acompanha —, anotadas com ``encerrada_em``, ``motivo`` e ``tem_cotacao``."""

    return _lista("encerradas", "encerrada_em", hoje)


def descartadas(hoje: dt.date | None = None) -> OportunidadeSalvaQuerySet:
    """As descartadas, anotadas com ``motivo``, ``descartada_em``,
    ``tem_cotacao`` e ``motivo_detalhe`` (o texto completo da lixeira)."""

    descartes = EventoOportunidadeSalva.objects.filter(
        oportunidade=OuterRef("pk"), tipo=EventoOportunidadeSalva.Tipo.DESCARTADA
    ).order_by("-ocorrido_em")
    return _lista("descartadas", "descartada_em", hoje).annotate(
        motivo_detalhe=Subquery(descartes.values("descricao")[:1])
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
        elif evento.tipo == Tipo.CORRECAO:
            item |= {"tipo": "correcao", "texto": evento.descricao or evento.get_tipo_display()}
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
    if salva.motivo == "acompanhando":
        porque = (
            "Está em \"Minhas participações\" no Compras.gov.br, o prazo passou e não há cotação no Licita: "
            "acompanhando o resultado (quem ganhou, marca e preço). Se a vigia achar proposta da empresa, "
            "a licitação volta para a Torre."
        )
        return {"tipo": "acompanhando", "data": salva.encerrada_em, "por": None, "porque": porque}
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
