"""O mercado de cada item (pedido da operação, 09/11/2026): dos itens em que
ele participou, quanto os órgãos pagaram nos últimos 3, 6, 12 e 24 meses,
quais marcas mais venceram e quanto **ele** ofereceu, em média, pelo mesmo item.

**O mesmo item = o item exato do catálogo (CATMAT)** — cadeira de rodas de
120 kg não é a de 150 kg. A descrição do edital é a do catálogo:

1. descrição → **PDM** (o tipo: "Cadeira de rodas manual para locomoção"),
   pelo maior nome de PDM que começa a descrição (`catalogo.Pdm`);
2. PDM → os itens do catálogo → o **código exato**, por semelhança da
   descrição (≥ `SEMELHANCA`);
3. código → **Pesquisa de Preços** (Dados Abertos), 24 meses.

O tipo (PDM) aparece só como referência. Menos de `POUCOS` compras no
período = "poucos dados". Os números ficam guardados (`MercadoDoItem`) e são
renovados 1x por semana pela conferência diária.
"""

from __future__ import annotations

import datetime as dt
import difflib
import logging
import re
import unicodedata
from collections import Counter
from decimal import Decimal
from statistics import mean, median

from django.utils import timezone

from .models import ItemParticipado, MercadoDoItem

logger = logging.getLogger(__name__)

PERIODOS = (3, 6, 12, 24)
SEMELHANCA = 0.98
POUCOS = 3
RENOVAR = dt.timedelta(days=7)


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z0-9]+", " ", texto).strip()


def achar_pdm(descricao: str):
    from apps.catalogo.models import Pdm

    alvo = normalizar(descricao)
    if not alvo:
        return None
    primeira = alvo.split()[0]
    candidatos = Pdm.objects.filter(nome_normalizado__startswith=primeira).only("codigo_pdm", "nome_pdm", "nome_normalizado")
    melhores = [p for p in candidatos if alvo.startswith(normalizar(p.nome_normalizado))]
    return max(melhores, key=lambda p: len(p.nome_normalizado), default=None)


def achar_catmat(descricao: str, itens_do_pdm: list[dict]) -> tuple[int | None, float]:
    alvo = normalizar(descricao)
    melhor, nota = None, 0.0
    for item in itens_do_pdm:
        r = difflib.SequenceMatcher(None, normalizar(item.get("descricaoItem") or ""), alvo).ratio()
        if r > nota:
            melhor, nota = item.get("codigoItem"), r
    return (melhor, nota) if nota >= SEMELHANCA else (None, nota)


def _resumo(compras: list[dict], hoje: dt.date) -> dict:
    periodos = {}
    for meses in PERIODOS:
        limite = hoje - dt.timedelta(days=round(meses * 30.44))
        no_periodo = [
            c for c in compras
            if c.get("precoUnitario") and c.get("dataCompra") and dt.date.fromisoformat(str(c["dataCompra"])[:10]) >= limite
        ]  # fmt: skip
        # Valor absurdo (mais de 5× ou menos de 1/5 da mediana) fica fora,
        # como no relatório da licitação.
        if no_periodo:
            meio = median(float(c["precoUnitario"]) for c in no_periodo)
            no_periodo = [c for c in no_periodo if meio / 5 <= float(c["precoUnitario"]) <= meio * 5]
        marcas = Counter((c.get("marca") or "").strip().upper() for c in no_periodo if (c.get("marca") or "").strip())
        periodos[str(meses)] = {
            "compras": len(no_periodo),
            "media": round(mean(float(c["precoUnitario"]) for c in no_periodo), 2) if no_periodo else None,
            "marcas": [{"marca": m, "vezes": n} for m, n in marcas.most_common(3)],
            "poucos_dados": len(no_periodo) < POUCOS,
        }
    return periodos


def atualizar(descricao: str, cliente, hoje: dt.date | None = None) -> MercadoDoItem:
    hoje = hoje or timezone.localdate()
    chave = normalizar(descricao)[:500]
    registro, _ = MercadoDoItem.objects.get_or_create(chave=chave, defaults={"descricao": descricao[:2000]})
    pdm = achar_pdm(descricao)
    inicio, fim = (hoje - dt.timedelta(days=731)).isoformat(), hoje.isoformat()
    registro.codigo_pdm = pdm.codigo_pdm if pdm else None
    registro.nome_pdm = pdm.nome_pdm if pdm else ""
    registro.codigo_catmat, registro.semelhanca = None, 0
    exato, grupo = {}, {}
    if pdm:
        codigo, nota = achar_catmat(descricao, cliente.itens_do_pdm(pdm.codigo_pdm))
        registro.codigo_catmat, registro.semelhanca = codigo, round(nota, 3)
        if codigo:
            exato = _resumo(cliente.precos_praticados("codigoItemCatalogo", codigo, inicio, fim), hoje)
        grupo = _resumo(cliente.precos_praticados("codigoPdm", pdm.codigo_pdm, inicio, fim), hoje)
    registro.dados = {"exato": exato, "grupo": grupo}
    registro.atualizado_em = timezone.now()
    registro.save()
    return registro


def renovar_todos(cliente, hoje: dt.date | None = None, limite: int = 30) -> int:
    """Os itens em que ele participou cujo mercado está velho (> 7 dias)."""

    agora = timezone.now()
    descricoes = {
        normalizar(d)[:500]: d
        for d in ItemParticipado.objects.exclude(descricao="").values_list("descricao", flat=True).distinct()
    }
    frescos = set(
        MercadoDoItem.objects.filter(chave__in=descricoes, atualizado_em__gte=agora - RENOVAR).values_list("chave", flat=True)
    )
    feitos = 0
    for chave, descricao in descricoes.items():
        if chave in frescos or feitos >= limite:
            continue
        try:
            atualizar(descricao, cliente, hoje)
            feitos += 1
        except Exception:  # noqa: BLE001
            logger.exception("Mercado: falha no item %s", descricao[:60])
    return feitos


def relatorio_de_mercado() -> list[dict]:
    """Um bloco por item exato em que ele participou: o mercado e a oferta dele."""

    ofertas: dict[str, list[Decimal]] = {}
    nomes: dict[str, str] = {}
    for item in ItemParticipado.objects.exclude(descricao=""):
        chave = normalizar(item.descricao)[:500]
        nomes.setdefault(chave, item.descricao)
        valor = item.valor_lance_final or item.valor_proposta_inicial
        if valor is not None:
            ofertas.setdefault(chave, []).append(valor)
    blocos = []
    for registro in MercadoDoItem.objects.filter(chave__in=nomes):
        dele = ofertas.get(registro.chave) or []
        blocos.append(
            {
                "descricao": nomes[registro.chave],
                "nome_pdm": registro.nome_pdm,
                "codigo_catmat": registro.codigo_catmat,
                "exato": registro.dados.get("exato") or {},
                "grupo": registro.dados.get("grupo") or {},
                "media_dele": round(float(sum(dele) / len(dele)), 2) if dele else None,
                "ofertas_dele": len(dele),
                "atualizado_em": registro.atualizado_em,
            }
        )
    blocos.sort(key=lambda b: -(b["exato"].get("24", {}).get("compras") or 0))
    return blocos
