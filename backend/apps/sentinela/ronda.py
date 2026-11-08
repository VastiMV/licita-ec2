"""A ronda da Sentinela: o que ela consulta sozinha, a cada 10 minutos, em
horário de trabalho — **só endereços que não pedem captcha**.

Para cada item em que a empresa tem proposta, numa compra que já passou da
sessão (fase 3 disputa ou 4 seleção de fornecedores):

- a **proposta** do item (situação, posição, pedido de desconto, anexo pedido);
- a **fase recursal** (quem recorreu, prazo de contrarrazões, decisão) — o
  recurso do item 22 do 56/2026 que ninguém viu;
- as **diligências**.

Descartadas também entram, mas só a proposta: é dela que vem a convocação
de anexo que traz a licitação de volta para a Torre.

A Sentinela faz a consulta na aba do Compras.gov, com a sessão da própria
página, e manda a resposta para `captura/` — a leitura é a mesma de quando
o Carlinhos abre a tela.
"""

from __future__ import annotations

import re

from apps.empresas.models import Empresa
from apps.licitacoes.models import ItemParticipado

FASES_DEPOIS_DA_SESSAO = {"3", "4"}
BASE = "/comprasnet-fase-externa/v1/compras"
CODIGO = re.compile(r"compra=(\d{17})")


def consultas() -> list[str]:
    cnpjs = list(Empresa.objects.filter(ativa=True).values_list("cnpj", flat=True))
    if not cnpjs:
        return []
    cnpj = cnpjs[0]
    caminhos: list[str] = []
    itens = (
        ItemParticipado.objects.filter(oportunidade__participacao__fase_compra__in=FASES_DEPOIS_DA_SESSAO)
        .exclude(vencedor_e_a_empresa=False)
        .exclude(situacao_proposta__in=["1", "2", "9", "5"])
        .select_related("oportunidade")
        .order_by("oportunidade_id", "numero_item")
    )
    for item in itens:
        achado = CODIGO.search(item.oportunidade.link_plataforma or "")
        if not achado:
            continue
        codigo, n = achado.group(1), item.numero_item
        caminhos.append(f"{BASE}/{codigo}/em-selecao-fornecedores/participacoes/{cnpj}/itens/{n}/propostas?filtro=2")
        if item.oportunidade.removida_em is not None:
            continue  # descartada: só o que pode ser convocação
        caminhos.append(f"{BASE}/{codigo}/itens/{n}/fase-recursal-fornecedor/{item.sessao_julgamento or 1}")
        caminhos.append(f"{BASE}/{codigo}/itens/{n}/participacoes/{cnpj}/diligencias")
    return caminhos
