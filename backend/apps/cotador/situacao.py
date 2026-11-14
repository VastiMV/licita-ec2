"""O selo e as faltas de uma cotação, para a lista do Cotador.

Veio de `apps/licitacoes/ciclo.py` quando o quadro antigo do Ciclo de
Licitação saiu (GEN-47, 14/11/2026). A regra não mudou.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from django.utils import timezone


@dataclass(frozen=True)
class Alerta:
    nivel: str  # "ok" | "neutro" | "aviso" | "alerta"
    texto: str



def _dias(de: dt.date, ate: dt.date) -> int:
    return (ate - de).days


def _itens(numeros: list[str]) -> str:
    """"item 3", "itens 3 e 4", "itens 1, 2 e 5"."""

    if len(numeros) == 1:
        return f"item {numeros[0]}"
    return f"itens {', '.join(numeros[:-1])} e {numeros[-1]}"



def _faltas_da_cotacao(cotacao) -> tuple[list[str], Alerta]:
    """O que falta, item a item, para a cotação virar proposta — e o selo.

    Três conferências, da mais grave para a menos grave:

    - **reserva acima do estimado** (vermelho): nem no piso o item fica
      abaixo do que o órgão estimou — entrar nele é prejuízo certo;
    - **sem preço de fornecedor** (amarelo): o item ainda não tem custo;
    - **preço acima do estimado** (amarelo): dá para entrar, mas o lance vai
      ter de descer até perto da reserva.

    O sistema não trava nada: é o que o cartão mostra como "falta".
    """

    from apps.cotador import formulas

    itens = list(cotacao.itens.all())
    calculados = [formulas.calcular_item(i, cotacao.padroes) for i in cotacao.para_calculo()]

    sem_preco, acima, reserva_acima = [], [], []
    for posicao, (item, calc) in enumerate(zip(itens, calculados), start=1):
        numero = item.numero_item or str(posicao)
        if calc.incompleto:
            sem_preco.append(numero)
            continue
        referencia = item.valor_referencia
        if not referencia:
            continue
        if calc.preco_reserva_unitario > referencia:
            reserva_acima.append(numero)
        elif calc.preco_final_unitario > referencia:
            acima.append(numero)

    faltas = []
    if reserva_acima:
        faltas.append(f"{_itens(reserva_acima)}: reserva acima do estimado — tirar ou entrar assim mesmo")
    if sem_preco:
        faltas.append(f"preço de fornecedor no {_itens(sem_preco)}")
    if acima:
        faltas.append(f"{_itens(acima)}: preço acima do estimado — rever markup")

    if reserva_acima:
        alerta = Alerta("alerta", "reserva acima do estimado")
    elif sem_preco:
        n = len(sem_preco)
        alerta = Alerta("aviso", f"{n} ite{'ns' if n > 1 else 'm'} sem preço")
    elif acima:
        alerta = Alerta("aviso", "preço acima do estimado")
    else:
        alerta = Alerta("ok", "cotação completa")
        faltas.append("gerar a proposta")
    return faltas, alerta



def situacao_da_cotacao(salva, hoje: dt.date | None = None) -> dict:
    """O selo e as faltas de uma salva na etapa Cotação."""

    hoje = hoje or timezone.localdate()
    faltas, alerta = _faltas_da_cotacao(salva.cotacao)
    alerta = _alerta_do_prazo(salva.data_encerramento_proposta, alerta, hoje)
    return {"nivel": alerta.nivel, "texto": alerta.texto, "faltas": faltas}


def _alerta_do_prazo(prazo: dt.date | None, alerta: Alerta, hoje: dt.date) -> Alerta:
    """Prazo de proposta até amanhã passa à frente de qualquer outro aviso
    (menos de outro alerta)."""

    if prazo:
        restantes = _dias(hoje, prazo)
        if 0 <= restantes <= 1 and alerta.nivel != "alerta":
            quando = "hoje" if restantes == 0 else "amanhã"
            return Alerta("alerta", f"propostas até {quando}")
    return alerta
