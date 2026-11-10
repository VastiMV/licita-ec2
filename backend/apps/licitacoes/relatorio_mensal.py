"""O relatório do mês (09/11/2026, pedido da operação: "simples e limpo").

Uma linha por mês: em quantas licitações participou (pelo mês do prazo da
proposta), quantas ganhou e quantas perdeu (pelo mês do resultado), o
faturamento (itens ganhos: valor × quantidade) e o lucro — só quando há
cotação no Licita (preço − custo da cotação, × quantidade).

**Perdeu por pouco:** itens perdidos por até `POUCO` (5%) do vencedor —
uma linha só na tela; a lista curta abre ao clicar.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from django.utils import timezone

from apps.cotador import formulas

from .models import OportunidadeSalva
from .relatorio import relatorio_do_item
from .torre import ORDEM, _cotacao_de, _participacao_de, _valor_unitario, etapa_do_item, rotulo_da_compra

POUCO = Decimal("5")
CENTAVO = Decimal("0.01")


def _custos(salva) -> dict[str, Decimal]:
    """Custo unitário de cada item, pela cotação do Licita (`{"22": 9800}`)."""

    cotacao = _cotacao_de(salva)
    if not cotacao:
        return {}
    custos = {}
    for linha, calculo in zip(cotacao.itens.all(), cotacao.para_calculo(), strict=False):
        custo = formulas.calcular_item(calculo, cotacao.padroes).custo_unitario
        if custo is not None:
            custos[str(linha.numero_item).lstrip("0") or "0"] = Decimal(str(custo))
    return custos


def _mes(data: dt.date | None) -> str | None:
    return f"{data:%Y-%m}" if data else None


def relatorio_mensal(meses: int = 12, hoje: dt.date | None = None) -> dict:
    hoje = hoje or timezone.localdate()
    chaves = []
    ano, mes = hoje.year, hoje.month
    for _ in range(meses):
        chaves.append(f"{ano:04d}-{mes:02d}")
        ano, mes = (ano - 1, 12) if mes == 1 else (ano, mes - 1)
    linhas = {
        c: {"mes": c, "participou": 0, "ganhou": 0, "perdeu": 0, "faturamento": Decimal(0), "lucro": None}
        for c in chaves
    }
    por_pouco = []

    salvas = OportunidadeSalva.objects.select_related("cotacao", "participacao").prefetch_related(
        "itens_participados__propostas", "documentos_financeiros", "entregas"
    )
    for salva in salvas:
        itens = list(salva.itens_participados.all())
        participacao = _participacao_de(salva)
        if not itens and not (participacao and participacao.proposta_cadastrada):
            continue
        if (m := _mes(salva.data_encerramento_proposta)) in linhas:
            linhas[m]["participou"] += 1
        if not itens:
            continue

        documentos = list(salva.documentos_financeiros.all())
        entregas = list(salva.entregas.all())
        custos = _custos(salva)
        ganhos, perdidos = [], []
        for item in itens:
            docs = [d for d in documentos if d.item_id in (None, item.pk)]
            ents = [e for e in entregas if e.item_id in (None, item.pk)]
            etapa = etapa_do_item(item, docs, ents, hoje).etapa
            if etapa is None:
                perdidos.append(item)
            elif ORDEM[etapa] >= ORDEM["homologado"]:
                ganhos.append(item)

        decididos = ganhos + perdidos
        quando = max((i.homologado_em for i in decididos if i.homologado_em), default=None)
        m = _mes(quando or salva.data_encerramento_proposta)
        if m not in linhas:
            continue
        linha = linhas[m]
        if ganhos:
            linha["ganhou"] += 1
        elif perdidos and len(perdidos) == len(itens):
            linha["perdeu"] += 1
        for item in ganhos:
            valor = _valor_unitario(item)
            if valor is None or item.quantidade is None:
                continue
            linha["faturamento"] += valor * item.quantidade
            custo = custos.get(item.numero_item.lstrip("0") or "0")
            if custo is not None:
                linha["lucro"] = (linha["lucro"] or Decimal(0)) + (valor - custo) * item.quantidade
        for item in perdidos:
            detalhe = relatorio_do_item(item)
            pct = detalhe["diferenca_percentual"]
            if pct is not None and Decimal(0) < pct <= POUCO:
                vencedor = detalhe["vencedor"] or {}
                por_pouco.append(
                    {
                        "mes": m,
                        "oportunidade_id": salva.pk,
                        "compra": rotulo_da_compra(salva),
                        "orgao_nome": salva.orgao_nome,
                        "item": item.numero_item,
                        "descricao": item.descricao,
                        "diferenca": detalhe["diferenca"],
                        "diferenca_percentual": pct,
                        "marca_vencedora": vencedor.get("marca") or "",
                    }
                )

    resultado = []
    for c in chaves:
        linha = linhas[c]
        linha["faturamento"] = linha["faturamento"].quantize(CENTAVO)
        if linha["lucro"] is not None:
            linha["lucro"] = linha["lucro"].quantize(CENTAVO)
        resultado.append(linha)
    por_pouco.sort(key=lambda p: (p["diferenca_percentual"], p["mes"]))
    return {"meses": resultado, "por_pouco": por_pouco, "pouco_percentual": POUCO}
