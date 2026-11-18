"""A IA do Radar (GEN-93, 17/11/2026): Claude Haiku julga cada compra.

**Por quê:** a primeira rodada em produção trouxe 168 compras. O Carlinhos não
vai olhar 168: o Radar tem que mostrar só as que realmente têm a ver com o
que ele trabalha, umas 3 ou 4 por dia. Palavra igual não quer dizer produto
igual ("bandana", "Grupo 3").

Regras da operação (17/11/2026):

1. **Referência:** os itens em que a Inside **participou de fato** e as
   compras em Oportunidades **salvas, descartadas e encerradas**.
2. **Complementa** o filtro de palavras: a IA só julga o que passou nele.
3. **Aprende com a lixeira:** o que ele removeu do Radar vai junto como
   exemplo do que ele **não** quer.
4. **Só as boas:** nota 0 a 10; abaixo de `NOTA_MINIMA` não aparece. Sem
   teto por dia: a precisão é que deixa a lista curta. Dia fraco mostra 1 ou
   nenhuma.
5. O motivo da nota não aparece na tela.

Sem a chave (`ANTHROPIC_API_KEY` vazia), a IA fica desligada e o Radar
funciona como antes (só o filtro de palavras). Erro ou recusa da IA: a compra
não entra agora e a próxima rodada tenta de novo.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from config.settings.environment import env

from .mercado import normalizar
from .models import ItemParticipado, OportunidadeSalva, SugestaoRadar

logger = logging.getLogger(__name__)

MODELO = "claude-haiku-5-5"
NOTA_MINIMA = 7
MAX_REFERENCIAS = 20
MAX_NEGATIVOS = 20
MAX_ITENS_DA_COMPRA = 10

SISTEMA = """Você filtra licitações públicas para uma empresa que vende ao governo.
O Radar acha compras abertas por palavras parecidas; o seu trabalho é dizer \
se a compra é mesmo de um produto que esta empresa trabalha.

Dê uma nota de 0 a 10:
- 10: o mesmo produto que a empresa já disputou ou salvou.
- 7 a 9: produto do mesmo tipo, que a empresa muito provavelmente vende.
- 4 a 6: parecido só no nome, ou só uma parte da compra tem a ver.
- 0 a 3: outro produto (a palavra coincidiu por acaso).

Regras:
- Compare os ITENS da compra com os itens de referência, não só o objeto.
- "Grupo 3", "Lote 2", "Item 5" são nomes de agrupamento, não produtos.
- Se a compra parece com algo que a empresa REMOVEU do Radar, a nota é baixa.
- Na dúvida, nota baixa: é melhor mostrar pouco e certo."""


class Avaliacao(BaseModel):
    nota: int
    motivo: str


_chave_recusada = False  # nesta execução (rodada/comando), não no banco


def ligada() -> bool:
    """Com chave, e sem a Anthropic ter recusado a chave nesta execução."""

    return bool(env.anthropic_api_key) and not _chave_recusada


def _parecidos(termo: str, textos: list[str], limite: int) -> list[str]:
    """Os textos com mais palavras em comum com o termo (sem repetir)."""

    palavras = set(normalizar(termo).split())
    vistos: set[str] = set()
    pontuados = []
    for texto in textos:
        chave = normalizar(texto)
        if not chave or chave in vistos:
            continue
        vistos.add(chave)
        comuns = sum(1 for p in palavras if any(t.startswith(p) for t in chave.split()))
        if comuns:
            pontuados.append((comuns, texto))
    pontuados.sort(key=lambda par: -par[0])
    return [t for _, t in pontuados[:limite]]


def referencias(termo: str) -> list[str]:
    """Itens em que participou de fato + itens das compras salvas,
    descartadas e encerradas (todas as `OportunidadeSalva`, removidas ou não)."""

    textos = list(
        ItemParticipado.objects.exclude(descricao="").values_list("descricao", flat=True)[:2000]
    )
    for itens in OportunidadeSalva.objects.values_list("itens", flat=True)[:2000]:
        for item in itens or []:
            if descricao := (item or {}).get("descricao_resumida"):
                textos.append(descricao)
    return _parecidos(termo, textos, MAX_REFERENCIAS)


def negativos(termo: str) -> list[str]:
    """O que ele mandou para a lixeira do Radar: o 1º item (o que casou) e o
    objeto, os mais parecidos com o termo primeiro, senão os mais recentes."""

    textos = []
    for sugestao in SugestaoRadar.objects.filter(removida_em__isnull=False).order_by("-removida_em")[:200]:
        item = (sugestao.itens or [{}])[0] or {}
        textos.append(f"{item.get('descricao_resumida') or ''} (compra: {sugestao.objeto[:120]})")
    parecidos = _parecidos(termo, textos, MAX_NEGATIVOS)
    return parecidos or textos[:MAX_NEGATIVOS]


def _lista(textos: list[str]) -> str:
    return "\n".join(f"- {t[:200]}" for t in textos) or "- (nenhum)"


def _pergunta(termo: str, objeto: str, itens: list[dict]) -> str:
    da_compra = [
        f"{i.get('descricao_resumida') or ''} — {(i.get('descricao_detalhada') or '')[:200]}"
        for i in itens[:MAX_ITENS_DA_COMPRA]
    ]
    return (
        f"Termo da busca: {termo}\n\n"
        f"Itens de referência (o que a empresa trabalha):\n{_lista(referencias(termo))}\n\n"
        f"O que a empresa REMOVEU do Radar (não quer):\n{_lista(negativos(termo))}\n\n"
        f"Compra candidata\nObjeto: {objeto[:400]}\n"
        f"Itens que casaram com o termo:\n{_lista(da_compra)}"
    )


def avaliar(termo: str, objeto: str, itens: list[dict], cliente=None) -> Avaliacao | None:
    """A nota da IA para a compra, ou `None` se a IA falhou ou recusou (a
    compra não entra agora; a próxima rodada tenta de novo)."""

    import anthropic

    cliente = cliente or anthropic.Anthropic(api_key=env.anthropic_api_key)
    try:
        resposta = cliente.messages.parse(
            model=MODELO,
            max_tokens=2000,
            system=SISTEMA,
            messages=[{"role": "user", "content": _pergunta(termo, objeto, itens)}],
            output_format=Avaliacao,
        )
    except (anthropic.AuthenticationError, anthropic.PermissionDeniedError, anthropic.BadRequestError) as exc:
        # Problema da CONTA, não da compra: chave errada ou sem crédito (teste
        # no servidor, 17/11/2026: 100 erros iguais na tela, duas vezes).
        # Para de perguntar nesta execução; nada que dependia dela entra.
        global _chave_recusada
        _chave_recusada = True
        motivo = (
            "sem crédito na conta da Anthropic (Billing)"
            if "credit balance" in str(exc)
            else "a Anthropic recusou a chave (ANTHROPIC_API_KEY)"
        )
        logger.error("Radar IA parada nesta rodada: %s.", motivo)
        return None
    except anthropic.APIError as exc:
        logger.warning('Radar IA: falhou ao julgar "%s": %s', objeto[:80], exc)
        return None
    if resposta.stop_reason == "refusal" or resposta.parsed_output is None:
        logger.warning('Radar IA: sem resposta (%s) para "%s"', resposta.stop_reason, objeto[:80])
        return None
    avaliacao = resposta.parsed_output
    avaliacao.nota = max(0, min(10, avaliacao.nota))
    return avaliacao
