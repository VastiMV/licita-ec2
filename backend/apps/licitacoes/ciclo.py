"""O Ciclo de Licitação — o quadro com uma coluna por etapa.

**A etapa é calculada, nunca gravada.** Ninguém escolhe etapa num select nem
arrasta cartão: ela sai do que existe. Hoje existem as três primeiras
etapas —

- **Oportunidade** — salva e ainda sem cotação;
- **Cotação** — com cotação salva no Cotador;
- **Proposta** — com proposta gerada no Cotador (`apps.propostas`);

— e as outras duas colunas (Disputa, Empenho) ficam vazias até as telas
delas existirem. Quando existirem, a regra cresce aqui, num lugar só.

**Prazo de proposta vencido sem proposta enviada sai do quadro.** É o
"prazo perdido": a licitação vai para Descartadas (ver `encerradas.py` —
Encerradas é só para quem participou do certame). Com proposta gerada, o
prazo vencer é o caminho normal e ela continua na coluna Proposta.

O limite de "salva há muito tempo sem cotação" é parâmetro da empresa na
proposta do fluxo; enquanto a tela de Parâmetros não existe, o padrão mora
em `DIAS_SEM_COTACAO`.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from django.utils import timezone

from .models import OportunidadeSalva
from .serializers import OportunidadeSalvaSerializer

# Padrão até existir Configurações › Parâmetros (ver docstring do módulo).
DIAS_SEM_COTACAO = 2

ETAPAS = [
    ("oportunidade", "Oportunidade"),
    ("cotacao", "Cotação"),
    ("proposta", "Proposta"),
    ("disputa", "Disputa"),
    ("empenho", "Empenho"),
]

# As etapas cuja tela ainda não existe — a coluna aparece, vazia.
ETAPAS_A_CONSTRUIR = {"disputa", "empenho"}


@dataclass(frozen=True)
class Alerta:
    nivel: str  # "ok" | "neutro" | "aviso" | "alerta"
    texto: str


def _cotacao_de(salva: OportunidadeSalva):
    """A cotação do Cotador, ou `None` — o acesso reverso de um-para-um
    levanta exceção quando não existe."""

    try:
        return salva.cotacao
    except OportunidadeSalva.cotacao.RelatedObjectDoesNotExist:
        return None


def _proposta_de(salva: OportunidadeSalva):
    try:
        return salva.proposta
    except OportunidadeSalva.proposta.RelatedObjectDoesNotExist:
        return None


def etapa_de(salva: OportunidadeSalva, hoje: dt.date) -> str:
    """"encerrada" ou uma das chaves de `ETAPAS`."""

    if _proposta_de(salva):
        return "proposta"
    if salva.expirada(hoje):
        return "encerrada"
    return "cotacao" if _cotacao_de(salva) else "oportunidade"


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


def situacao_da_cotacao(salva: OportunidadeSalva, hoje: dt.date | None = None) -> dict:
    """O selo e as faltas de uma salva na etapa Cotação — o mesmo do cartão
    do quadro, para a lista do Cotador não divergir dele."""

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


def _cartao(salva: OportunidadeSalva, etapa: str, hoje: dt.date) -> dict:
    prazo = salva.data_encerramento_proposta
    cotacao = _cotacao_de(salva)

    if etapa == "oportunidade":
        dias_salva = _dias(timezone.localtime(salva.criada_em).date(), hoje)
        if dias_salva > DIAS_SEM_COTACAO:
            alerta = Alerta("aviso", f"salva há {dias_salva} dias, sem cotação")
        elif dias_salva == 0:
            alerta = Alerta("neutro", "salva hoje")
        else:
            alerta = Alerta("neutro", f"salva há {dias_salva} dia{'s' if dias_salva > 1 else ''}")
        faltas = ["iniciar a cotação para saber se dá"]
        if not salva.itens:
            faltas.append("edital salvo sem itens — conferir no PNCP")
        valor_cotado = None
        pendencias = None
    elif etapa == "proposta":
        proposta = _proposta_de(salva)
        gerada = timezone.localtime(proposta.gerada_em)
        alerta = Alerta("ok", f"proposta gerada em {gerada:%d/%m}")
        gerado = any(a.origem == "gerado" for a in proposta.arquivos.all())
        faltas = [
            *([] if proposta.empresa_id else ["escolher a empresa (CNPJ) da proposta"]),
            *([] if gerado else ["gerar a proposta comercial (Word)"]),
            "enviar a proposta na plataforma",
        ]
        valor_cotado = float(proposta.valor)
        pendencias = None
    else:
        pendencias = cotacao.totais().pendencias
        valor_cotado = float(cotacao.valor_cotado)
        faltas, alerta = _faltas_da_cotacao(cotacao)

    if etapa != "encerrada":
        alerta = _alerta_do_prazo(prazo, alerta, hoje)

    return {
        "id": salva.pk,
        "etapa": etapa,
        "uasg": salva.uasg,
        "municipio": salva.municipio,
        "uf": salva.uf,
        "objeto": salva.objeto,
        "data_encerramento_proposta": prazo,
        "valor_total_estimado": (
            float(salva.valor_total_estimado) if salva.valor_total_estimado is not None else None
        ),
        "cotacao_id": cotacao.pk if cotacao else None,
        "proposta_id": proposta.pk if (proposta := _proposta_de(salva)) else None,
        # Na etapa Oportunidade o cartão abre o visualizador da salva, que
        # precisa do registro inteiro (o snapshot do edital). Com cotação, o
        # Cotador carrega a dele pelo id.
        "salva": OportunidadeSalvaSerializer(salva).data if etapa == "oportunidade" else None,
        "valor_cotado": valor_cotado,
        "pendencias": pendencias,
        "alerta": {"nivel": alerta.nivel, "texto": alerta.texto},
        # Em ordem de gravidade; o cartão mostra as primeiras.
        "faltas": faltas,
    }


def montar_quadro(hoje: dt.date | None = None) -> dict:
    """O quadro inteiro: as cinco colunas, o resumo do dia e quantas
    encerradas ficaram de fora."""

    hoje = hoje or timezone.localdate()
    salvas = (
        OportunidadeSalva.objects.ativas()
        .select_related("cotacao", "proposta")
        .prefetch_related("cotacao__itens__ofertas", "proposta__arquivos")
    )

    por_etapa: dict[str, list[dict]] = {chave: [] for chave, _ in ETAPAS}
    encerradas = 0
    for salva in salvas:
        etapa = etapa_de(salva, hoje)
        if etapa == "encerrada":
            encerradas += 1
            continue
        por_etapa[etapa].append(_cartao(salva, etapa, hoje))

    # Quem vence primeiro vem primeiro — é por onde a manhã começa. Sem
    # prazo vai para o fim.
    for cartoes in por_etapa.values():
        cartoes.sort(key=lambda c: (c["data_encerramento_proposta"] or dt.date.max, c["id"]))

    todos = [c for cartoes in por_etapa.values() for c in cartoes]
    fim_da_semana = hoje + dt.timedelta(days=6 - hoje.weekday())

    return {
        "hoje": hoje,
        "resumo": {
            "prazo_ate_amanha": sum(1 for c in todos if c["alerta"]["nivel"] == "alerta"),
            "prazo_nesta_semana": sum(
                1
                for c in todos
                if c["data_encerramento_proposta"]
                and hoje <= c["data_encerramento_proposta"] <= fim_da_semana
            ),
            "salvas_sem_cotacao": sum(
                1 for c in por_etapa["oportunidade"] if c["alerta"]["nivel"] == "aviso"
            ),
            "cotacoes_com_pendencia": sum(1 for c in por_etapa["cotacao"] if c["pendencias"]),
        },
        "colunas": [
            {
                "etapa": chave,
                "rotulo": rotulo,
                "disponivel": chave not in ETAPAS_A_CONSTRUIR,
                "total_estimado": sum(c["valor_total_estimado"] or 0 for c in por_etapa[chave]),
                "cartoes": por_etapa[chave],
            }
            for chave, rotulo in ETAPAS
        ],
        # Hoje só existe "vencida" (prazo de proposta perdido). Concluídas,
        # perdidas e descartadas chegam com as etapas que as produzem.
        "encerradas": {"vencidas": encerradas, "concluidas": 0},
        "dias_sem_cotacao": DIAS_SEM_COTACAO,
    }
