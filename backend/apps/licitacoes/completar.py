"""Completar pelo PNCP a salva que chegou sem dados (10/11/2026).

A Sentinela cria a salva com o que o Compras.gov.br mandou na participação:
às vezes **sem o nome do órgão** (Dispensa 27/2026, UASG 443034 — o cartão da
Torre mostrava o objeto no lugar do órgão) e **sempre sem os itens** (o
Cotador abre vazio e não deixa registrar preço). O hábito da operação é
aceitar o cadastro no Compras.gov primeiro e cotar no Licita depois, então
isso acontece com toda compra que entra por esse caminho.

Aqui a salva ganha o que a busca teria gravado: órgão, cidade, UF, objeto,
valor e os itens, do PNCP. **Só o que está vazio** é preenchido — nada que já
existe é trocado. Quem chama: a Sentinela (em segundo plano, ver
`tasks.completar_salva`) e a conferência diária (7h45).
"""

from __future__ import annotations

import datetime as dt
import logging
from decimal import Decimal

from apps.integracoes.clients.pncp import PncpClient
from apps.integracoes.plataformas import identificar_plataforma, plataforma_padrao

from .models import EventoOportunidadeSalva, OportunidadeSalva, montar_texto_busca

logger = logging.getLogger(__name__)

CAMPOS_DE_TEXTO = ("orgao_nome", "municipio", "uf", "objeto", "modalidade")


def falta_dados(salva: OportunidadeSalva) -> bool:
    """Sem órgão ou sem itens: o cartão e o Cotador ficam incompletos."""

    return not salva.orgao_nome or not salva.itens


def completar_pelo_pncp(salva: OportunidadeSalva, pncp: PncpClient | None = None) -> list[str]:
    """Preenche os campos vazios da salva com o PNCP e devolve os nomes dos
    campos preenchidos (vazio = nada a fazer). Erro do PNCP sobe: quem chama
    decide (a tarefa tenta de novo na próxima ronda)."""

    if not falta_dados(salva) or not (salva.cnpj_orgao and salva.ano_compra and salva.sequencial_compra):
        return []

    from .services import _montar_oportunidade

    pncp = pncp or PncpClient()
    chave = {"cnpj": salva.cnpj_orgao, "ano": salva.ano_compra, "sequencial": salva.sequencial_compra}
    detalhe = pncp.detalhar_compra(**chave)
    preenchidos: list[str] = []

    novos = {
        "orgao_nome": detalhe.get("orgao_nome"),
        "municipio": detalhe.get("municipio_nome"),
        "uf": detalhe.get("uf"),
        "objeto": detalhe.get("objeto"),
        "modalidade": detalhe.get("modalidade"),
    }
    for campo in CAMPOS_DE_TEXTO:
        valor = (novos[campo] or "").strip()
        if valor and not getattr(salva, campo):
            limite = OportunidadeSalva._meta.get_field(campo).max_length
            setattr(salva, campo, valor[:limite] if limite else valor)
            preenchidos.append(campo)

    if salva.valor_total_estimado is None and detalhe.get("valor_total_estimado") is not None:
        salva.valor_total_estimado = Decimal(str(detalhe["valor_total_estimado"]))
        preenchidos.append("valor_total_estimado")
    if salva.data_publicacao is None and detalhe.get("data_publicacao"):
        salva.data_publicacao = dt.date.fromisoformat(detalhe["data_publicacao"])
        preenchidos.append("data_publicacao")

    if not salva.itens:
        itens = pncp.listar_itens(**chave)
        if itens:
            plataforma = identificar_plataforma(salva.link_plataforma) or plataforma_padrao()
            contratacao = {
                "cnpj_orgao": salva.cnpj_orgao,
                "ano_compra": salva.ano_compra,
                "sequencial_compra": salva.sequencial_compra,
                "uasg": salva.uasg,
                "orgao_nome": salva.orgao_nome,
                "uf": salva.uf,
                "municipio": salva.municipio,
                "objeto": salva.objeto,
                "modalidade": salva.modalidade,
                "situacao": salva.situacao or detalhe.get("situacao_nome"),
                "valor_total_estimado": detalhe.get("valor_total_estimado"),
                "data_publicacao": salva.data_publicacao.isoformat() if salva.data_publicacao else None,
                "data_encerramento_proposta": (
                    salva.data_encerramento_proposta.isoformat() if salva.data_encerramento_proposta else None
                ),
                "link_plataforma": salva.link_plataforma,
            }
            salva.itens = [_montar_oportunidade(contratacao, item, plataforma) for item in itens]
            preenchidos.append("itens")

    if not preenchidos:
        return []
    salva.texto_busca = montar_texto_busca(salva.objeto, salva.itens or [])
    salva.save(update_fields=[*preenchidos, "texto_busca"])
    salva.registrar(
        EventoOportunidadeSalva.Tipo.CORRECAO,
        descricao="Dados completados pelo PNCP (a compra veio da Sentinela sem eles): "
        + ", ".join(NOMES.get(c, c) for c in preenchidos)
        + ".",
        dados={"campos": preenchidos},
    )
    return preenchidos


NOMES = {
    "orgao_nome": "órgão",
    "municipio": "cidade",
    "uf": "UF",
    "objeto": "objeto",
    "modalidade": "modalidade",
    "valor_total_estimado": "valor estimado",
    "data_publicacao": "data de publicação",
    "itens": "itens",
}


def completar_as_que_faltam(pncp: PncpClient | None = None) -> dict[str, int]:
    """Todas as salvas ativas sem órgão ou sem itens. Uma com problema não
    para as outras."""

    pncp = pncp or PncpClient()
    resumo = {"completadas": 0, "falhas": 0}
    for salva in OportunidadeSalva.objects.ativas().filter(_sem_dados()):
        try:
            resumo["completadas"] += int(bool(completar_pelo_pncp(salva, pncp)))
        except Exception:  # noqa: BLE001
            resumo["falhas"] += 1
            logger.exception("Completar pelo PNCP: falha na salva %s", salva.pk)
    return resumo


def _sem_dados():
    from django.db.models import Q

    return Q(orgao_nome="") | Q(itens=[])
