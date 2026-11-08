"""A lixeira da Torre (decisão da operação, 08/11/2026).

Para o Carlinhos é **uma coisa só**: em qualquer cartão de Preparar ou de
Disputar, um clique, uma pergunta, e a licitação vai para Descartadas. As
diferenças técnicas ficam aqui:

- **A pergunta diz o que ele tem lá.** Se a Sentinela já leu os itens e há
  preço lançado, a pergunta mostra item, marca, valor e posição ("Você tem
  preço cadastrado no item 2… Deseja prosseguir?"). Se ainda não leu, diz que
  não conferiu. Nunca bloqueia.
- **O motivo fica completo**: quem descartou, quando, em que etapa e com que
  preço — "ele vai esquecer e vai perguntar". Vai para o histórico
  (`EventoOportunidadeSalva.Tipo.DESCARTADA`) e é o que Descartadas mostra.
- **No Compras.gov, só o favorito sai** (`sentinela.Tarefa` DESFAVORITAR).
  Com preço lançado a compra continua em "Minhas participações" — o
  Compras.gov fica "poluído"; quem fica limpo é o Licita.
- **A Sentinela nunca traz de volta** o que foi descartado
  (`sentinela/ingestao.py`), **exceto convocação**: aí volta para a Torre,
  em vermelho (`VOLTOU`).
"""

from __future__ import annotations

import datetime as dt
import re
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import EventoOportunidadeSalva, OportunidadeSalva, nome_de_usuario
from .torre import _participacao_de, avaliar

CODIGO_DA_COMPRA = re.compile(r"compra=(\d{17})")


def _moeda(valor: Decimal | None) -> str:
    if valor is None:
        return ""
    texto = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def _marca_e_modelo(marca: str, modelo: str) -> str:
    """"Dellamed" + "D600" → "Dellamed D600"; "Movement" + "Movement LX" → "Movement LX"."""

    marca, modelo = (marca or "").strip(), (modelo or "").strip()
    if modelo.lower().startswith(marca.lower()):
        return modelo or marca
    return f"{marca} {modelo}".strip()


def itens_com_preco(salva: OportunidadeSalva) -> list[dict]:
    """Os itens em que a empresa lançou preço, como a Sentinela os leu."""

    itens = []
    for item in salva.itens_participados.all():
        valor = item.valor_lance_final or item.valor_proposta_inicial
        if valor is None and not item.marca:
            continue
        itens.append(
            {
                "numero": item.numero_item,
                "descricao": item.descricao,
                "marca": _marca_e_modelo(item.marca, item.modelo),
                "valor": valor,
                "classificacao": item.classificacao,
            }
        )
    return itens


def _texto_do_item(item: dict) -> str:
    partes = [p for p in (item["marca"], _moeda(item["valor"])) if p]
    if item["classificacao"]:
        partes.append(f"{item['classificacao']}º lugar")
    return f"item {item['numero']}" + (f" ({', '.join(partes)})" if partes else "")


def resumo(salva: OportunidadeSalva, hoje: dt.date | None = None) -> dict:
    """O que a lixeira mostra antes de confirmar."""

    hoje = hoje or timezone.localdate()
    cartao, _ = avaliar(salva, hoje)
    participacao = _participacao_de(salva)
    itens = itens_com_preco(salva)
    conferido = bool(itens) or bool(participacao and participacao.proposta_cadastrada is not None)
    if itens:
        pergunta = "Você tem preço cadastrado no " + "; no ".join(_texto_do_item(i) for i in itens) + "."
    elif conferido:
        pergunta = "Você não tem preço cadastrado nesta compra."
    else:
        pergunta = "Ainda não conferi se você tem preço cadastrado nesta compra."
    return {
        "etapa": cartao["etapa"] if cartao else None,
        "etapa_rotulo": cartao["etapa_rotulo"] if cartao else "",
        "conferido": conferido,
        "itens_com_preco": itens,
        "pergunta": f"{pergunta} Deseja prosseguir?",
        "tira_favorito": bool(CODIGO_DA_COMPRA.search(salva.link_plataforma or "")),
    }


@transaction.atomic
def descartar(salva: OportunidadeSalva, por, hoje: dt.date | None = None) -> EventoOportunidadeSalva:
    """Tira da Torre, grava o motivo completo e pede à Sentinela para tirar o
    favorito no Compras.gov."""

    from apps.sentinela.models import Tarefa

    agora = timezone.now()
    antes = resumo(salva, hoje)
    etapa = antes["etapa_rotulo"] or "fora do quadro"
    descricao = (
        f"Descartada manualmente por {nome_de_usuario(por)} em {timezone.localtime(agora):%d/%m/%Y}, "
        f"na etapa {etapa}."
    )
    if antes["itens_com_preco"]:
        descricao += " Tinha preço no " + "; no ".join(_texto_do_item(i) for i in antes["itens_com_preco"]) + "."
    elif not antes["conferido"]:
        descricao += " Os itens ainda não tinham sido conferidos no Compras.gov."

    salva.removida_em = agora
    salva.removida_por = por
    salva.removida_por_nome = nome_de_usuario(por)[:150]
    salva.save(update_fields=["removida_em", "removida_por", "removida_por_nome"])
    evento = salva.registrar(
        EventoOportunidadeSalva.Tipo.DESCARTADA,
        autor=por,
        descricao=descricao,
        dados={
            "etapa": antes["etapa"],
            "itens_com_preco": [{**i, "valor": str(i["valor"]) if i["valor"] is not None else None} for i in antes["itens_com_preco"]],
            "conferido": antes["conferido"],
        },
    )
    if codigo := CODIGO_DA_COMPRA.search(salva.link_plataforma or ""):
        Tarefa.objects.create(tipo=Tarefa.Tipo.DESFAVORITAR, compra=codigo.group(1), oportunidade=salva)
    return evento


def voltar_por_convocacao(salva: OportunidadeSalva, motivo: str) -> bool:
    """Descartada com convocação volta para a Torre (em vermelho: a etiqueta
    de convocação faz o resto). Devolve True se voltou."""

    if salva.removida_em is None:
        return False
    if OportunidadeSalva.objects.ativas().filter(
        cnpj_orgao=salva.cnpj_orgao, ano_compra=salva.ano_compra, sequencial_compra=salva.sequencial_compra
    ).exists():
        return False
    salva.removida_em = None
    salva.removida_por = None
    salva.removida_por_nome = ""
    salva.save(update_fields=["removida_em", "removida_por", "removida_por_nome"])
    salva.registrar(
        EventoOportunidadeSalva.Tipo.VOLTOU,
        descricao=f"Voltou para a Torre sozinha: {motivo}.",
    )
    return True

