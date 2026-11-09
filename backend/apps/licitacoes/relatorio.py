"""O relatório da licitação: item a item, quem ganhou (ou está em 1º), com
que marca e modelo, por quanto, e quanto a empresa ficou de diferença.

Fonte: a lista de propostas de todos os participantes (`PropostaDoItem`),
que a Sentinela lê no Compras.gov.br. Só os itens em que a empresa
participou — os outros nem entram no Licita (pedido da operação, 08/11/2026).

**Valor atípico:** proposta absurda (ex.: R$ 199.733,32 numa cadeira de rodas
de R$ 1.200 — Cubatão 55/2026, item 2) é marcada e fica fora da mediana.
Atípico = mais de 5× ou menos de 1/5 da mediana do item.
"""

from __future__ import annotations

from collections import Counter
from decimal import Decimal
from statistics import median

from .torre import PERDEU_A_VEZ, posicao_efetiva, proposta_vencedora, rotulo_da_compra

FATOR_ATIPICO = Decimal(5)
CENTAVO = Decimal("0.01")


def _dinheiro(valor: Decimal | None) -> Decimal | None:
    return None if valor is None else valor.quantize(CENTAVO)


def _atipicos(valores: list[Decimal]) -> tuple[Decimal | None, set[int]]:
    if not valores:
        return None, set()
    meio = Decimal(str(median(valores)))
    if meio <= 0:
        return meio, set()
    fora = {i for i, v in enumerate(valores) if v > meio * FATOR_ATIPICO or v * FATOR_ATIPICO < meio}
    dentro = [v for i, v in enumerate(valores) if i not in fora]
    return (Decimal(str(median(dentro))) if dentro else meio), fora


def _proposta(p, atipica: bool) -> dict:
    return {
        "classificacao": p.classificacao,
        "fornecedor": p.nome,
        "cnpj": p.cnpj,
        "uf": p.uf,
        "marca": p.marca,
        "modelo": p.modelo,
        "valor": _dinheiro(p.valor_final),
        "situacao": p.situacao,
        "caiu": p.situacao in PERDEU_A_VEZ,
        "da_empresa": p.da_empresa,
        "atipica": atipica,
    }


def relatorio_do_item(item) -> dict:
    propostas = sorted(item.propostas.all(), key=lambda p: (p.classificacao or 10**6, p.pk))
    com_valor = [p for p in propostas if p.valor_final is not None]
    mediana, fora = _atipicos([p.valor_final for p in com_valor])
    atipicas = {com_valor[i].pk for i in fora}

    homologado = item.vencedor_e_a_empresa is not None
    vencedora = proposta_vencedora(propostas) if propostas else None
    empresa = next((p for p in propostas if p.da_empresa), None)
    valor_dele = empresa.valor_final if empresa else item.valor_lance_final or item.valor_proposta_inicial
    valor_vencedor = vencedora.valor_final if vencedora else None

    diferenca = percentual = None
    if valor_dele is not None and valor_vencedor:
        diferenca = _dinheiro(valor_dele - valor_vencedor)
        percentual = ((valor_dele - valor_vencedor) / valor_vencedor * 100).quantize(Decimal("0.1"))

    marcas = Counter(p.marca.strip().upper() for p in propostas if p.marca.strip())
    return {
        "numero": item.numero_item,
        "descricao": item.descricao,
        "quantidade": item.quantidade,
        "participantes": len(propostas),
        "lido_em": item.propostas_lidas_em,
        "homologado": homologado,
        "empresa_venceu": item.vencedor_e_a_empresa,
        "vencedor": _proposta(vencedora, vencedora.pk in atipicas) if vencedora else None,
        "empresa": {
            "classificacao": empresa.classificacao if empresa else item.classificacao,
            "posicao_efetiva": posicao_efetiva(item),
            "marca": empresa.marca if empresa else item.marca,
            "modelo": empresa.modelo if empresa else item.modelo,
            "valor": _dinheiro(valor_dele),
        },
        "diferenca": diferenca,
        "diferenca_percentual": percentual,
        "mediana": _dinheiro(mediana),
        "marcas": [{"marca": m, "propostas": n} for m, n in marcas.most_common(5)],
        "propostas": [_proposta(p, p.pk in atipicas) for p in propostas],
    }


def relatorio_da_compra(salva) -> dict:
    itens = [relatorio_do_item(i) for i in salva.itens_participados.prefetch_related("propostas")]
    return {
        "id": salva.pk,
        "compra": rotulo_da_compra(salva),
        "orgao_nome": salva.orgao_nome,
        "uasg": salva.uasg,
        "objeto": salva.objeto,
        "itens": itens,
        "resumo": {
            "itens": len(itens),
            "com_propostas": sum(1 for i in itens if i["participantes"]),
            "ganhos": sum(1 for i in itens if i["empresa_venceu"]),
            "perdidos": sum(1 for i in itens if i["empresa_venceu"] is False),
        },
    }
