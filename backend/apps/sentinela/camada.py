"""Os números da camada de disputa: o que a Sentinela mostra ao lado da tela
do Compras.gov.br durante a disputa, item a item.

Tudo vem da cotação do Licita (`apps/cotador/formulas.py`), sem conta nova:

- **teto** — o valor de referência do item no edital;
- **ideal** — o preço que a cotação propõe (lucro alvo);
- **piso** — o preço de reserva (lucro mínimo): abaixo dele, não vale;
- **custo** — o que a empresa paga por unidade, com frete e extras;
- **lucro no ideal** — por unidade.
"""

from __future__ import annotations

from apps.cotador import formulas
from apps.licitacoes.models import OportunidadeSalva


def numeros_da_compra(codigo: str) -> dict | None:
    salva = OportunidadeSalva.objects.ativas().filter(link_plataforma__contains=f"compra={codigo}").first()
    if not salva:
        return None
    try:
        cotacao = salva.cotacao
    except OportunidadeSalva.cotacao.RelatedObjectDoesNotExist:
        return {"compra": codigo, "oportunidade_id": salva.pk, "tem_cotacao": False, "itens": []}

    itens = []
    padroes = cotacao.padroes
    for linha, calculo in zip(cotacao.itens.all(), cotacao.para_calculo(), strict=True):
        calculado = formulas.calcular_item(calculo, padroes)
        itens.append(
            {
                "numero": linha.numero_item,
                "descricao": linha.descricao,
                "quantidade": linha.quantidade,
                "teto": linha.valor_referencia,
                "ideal": calculado.preco_final_unitario,
                "piso": calculado.preco_reserva_unitario,
                "custo": calculado.custo_unitario,
                "lucro_no_ideal": calculado.lucro_unitario,
                "incompleto": calculado.incompleto,
            }
        )
    return {"compra": codigo, "oportunidade_id": salva.pk, "tem_cotacao": True, "itens": itens}
