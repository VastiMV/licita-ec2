"""A Torre de Controle — o ciclo inteiro, da oportunidade ao pagamento.

Mesma regra do `ciclo.py`: **a etapa é calculada, nunca gravada.** O que
muda são as entradas. Além da cotação, contam os fatos de fora, guardados
nos models da Torre (ver `models.py`):

- `ParticipacaoCompra` e `ItemParticipado` — o que o Compras.gov.br diz da
  compra e de cada item da empresa (pela Sentinela);
- `ItemParticipado.vencedor_e_a_empresa` — o resultado homologado no PNCP;
- `DocumentoFinanceiro` e `Entrega` — contrato, ata, empenho, OF,
  liquidação, pagamento, entrega.

**A etapa é do item.** Cada item da empresa tem a sua; o cartão da licitação
fica na etapa do item que está mais adiante. Item perdido (desclassificado,
inabilitado, homologado para outro) não conta; se todos se perderam, a
licitação sai para Encerradas.

**O PDF da proposta não define etapa.** Ele é a proposta ajustada, enviada
depois de ganhar, durante o julgamento (convocação de anexo).

Desde 08/11/2026 é a tela inicial e substitui o quadro do `ciclo.py` (que
sai em `feat-remover-legado`). A explicação completa, para quem chega, está
em docs/TORRE.md.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from decimal import Decimal

from django.utils import timezone

from .models import OportunidadeSalva
from .serializers import OportunidadeSalvaSerializer

ESTAGIOS: list[tuple[str, str, list[tuple[str, str]]]] = [
    (
        "preparar",
        "Preparar",
        [("oportunidade", "Oportunidade"), ("cotacao", "Cotação"), ("cadastro_proposta", "Cadastro de proposta")],
    ),
    (
        "disputar",
        "Disputar",
        [
            ("disputa", "Disputa"),
            ("aguardando_julgamento", "Aguardando julgamento"),
            ("julgado_habilitado", "Julgado e habilitado"),
            ("aguardando_adjudicacao", "Aguardando adjudicação"),
            ("homologado", "Homologado"),
        ],
    ),
    ("contratar", "Contratar", [("contrato", "Contrato"), ("empenho", "Empenho / Ordem de Fornecimento")]),
    ("receber", "Receber", [("entrega", "Entrega"), ("liquidado", "Liquidado"), ("recebido", "Recebido")]),
]

ETAPAS = [chave for _, _, etapas in ESTAGIOS for chave, _ in etapas]
ROTULO = {chave: rotulo for _, _, etapas in ESTAGIOS for chave, rotulo in etapas}
ESTAGIO_DA_ETAPA = {chave: estagio for estagio, _, etapas in ESTAGIOS for chave, _ in etapas}
ORDEM = {chave: posicao for posicao, chave in enumerate(ETAPAS)}

# Códigos do Compras.gov.br (comprasnet-fase-externa/v1/enums).
FASES_ITEM_EM_DISPUTA = {
    "AA", "LS", "LA", "LF", "AL", "FE", "RA", "AF", "AM", "DM", "A7", "D7", "DF", "B3", "JT",
}  # fmt: skip
FASES_ITEM_DEPOIS_DA_DISPUTA = {"E", "JE", "HE", "PE", "PR", "JR"}
FASES_ITEM_EM_RECURSO = {"AR", "AC", "D1", "D2"}
FASE_ITEM_ADJUDICADO = "AE"
FASE_COMPRA_EM_DISPUTA = "3"
FASES_COMPRA_ANTES_DA_SESSAO = {"", "1", "5", "6", "99"}

PROPOSTA_DESCLASSIFICADA = {"1", "2", "9"}
PROPOSTA_ACEITA = "3"
FORNECEDOR_HABILITADO = "4"
FORNECEDOR_INABILITADO = "5"
PROPOSTA_ADJUDICADA = "6"

CENTAVO = Decimal("0.01")

# A única plataforma que a Sentinela lê. Licitação de outro portal não espera
# por ela (ficaria presa): segue a regra de prazo de sempre.
PLATAFORMA_COM_SENTINELA = "compras_gov"

SITUACOES_QUE_ENCERRAM = {"RE": "Revogada", "AN": "Anulada", "FR": "Fracassada", "DE": "Deserta"}


@dataclass(frozen=True)
class Etiqueta:
    nivel: str  # "alerta" | "aviso" | "info"
    texto: str


@dataclass
class EtapaDoItem:
    etapa: str | None  # None = item perdido
    perdido: str = ""
    perdendo: bool = False
    etiquetas: tuple[Etiqueta, ...] = ()


def _tipos(documentos) -> set[str]:
    return {d.tipo for d in documentos}


def etapa_do_item(item, documentos, entregas, hoje: dt.date) -> EtapaDoItem:
    """A etapa de um item da empresa, do fato mais adiantado para trás.

    `documentos` e `entregas` são os do item **mais** os da compra inteira
    (sem item), que valem para todos os itens ganhos.
    """

    if item.vencedor_e_a_empresa is False:
        return EtapaDoItem(None, perdido="homologado para outro fornecedor")
    if item.situacao_proposta in PROPOSTA_DESCLASSIFICADA:
        return EtapaDoItem(None, perdido="proposta desclassificada")
    if item.situacao_proposta == FORNECEDOR_INABILITADO:
        return EtapaDoItem(None, perdido="fornecedor inabilitado")

    tipos = _tipos(documentos)
    if "pagamento" in tipos:
        return EtapaDoItem("recebido")
    if "liquidacao" in tipos:
        return EtapaDoItem("liquidado")
    if entregas:
        return EtapaDoItem("entrega")
    if tipos & {"empenho", "ordem_fornecimento"}:
        return EtapaDoItem("empenho")
    if tipos & {"contrato", "ata"}:
        return EtapaDoItem("contrato")

    if (
        item.situacao_proposta == PROPOSTA_ADJUDICADA
        or item.vencedor_e_a_empresa
        or item.homologado_em
        or item.fase_item == FASE_ITEM_ADJUDICADO
    ):
        return EtapaDoItem("homologado")

    if item.situacao_proposta == FORNECEDOR_HABILITADO:
        recurso_aberto = item.fase_item in FASES_ITEM_EM_RECURSO or (
            item.recurso_ate is not None and item.recurso_ate >= hoje
        )
        if recurso_aberto:
            etiqueta = (
                Etiqueta("aviso", f"recurso até {item.recurso_ate:%d/%m}")
                if item.recurso_ate
                else Etiqueta("aviso", "em fase de recurso")
            )
            return EtapaDoItem("julgado_habilitado", etiquetas=(etiqueta,))
        return EtapaDoItem("aguardando_adjudicacao")
    if item.situacao_proposta == PROPOSTA_ACEITA:
        return EtapaDoItem("julgado_habilitado")

    perdendo = bool(item.classificacao and item.classificacao > 1)
    if item.fase_item in FASES_ITEM_EM_DISPUTA:
        return EtapaDoItem("disputa", perdendo=perdendo)
    if item.fase_item in FASES_ITEM_DEPOIS_DA_DISPUTA or item.classificacao:
        return EtapaDoItem("aguardando_julgamento", perdendo=perdendo)
    return EtapaDoItem("cadastro_proposta")


def _valor_unitario(item) -> Decimal | None:
    """O valor que vale agora: homologado > negociado > lance > proposta."""

    for valor in (
        item.valor_homologado,
        item.valor_negociado,
        item.valor_lance_final,
        item.valor_proposta_inicial,
    ):
        if valor is not None:
            return valor
    return None


@dataclass
class Saida:
    para: str  # "encerradas" | "descartadas"
    motivo: str


# Código da compra no Compras.gov: UASG (6) + modalidade (2) + número (5) + ano (4).
MODALIDADE_COMPRAS_GOV = {
    "05": "Pregão",
    "06": "Dispensa",
    "07": "Inexigibilidade",
    "03": "Concorrência",
    "04": "Concorrência",
    "20": "Concurso",
}
_CODIGO_DA_COMPRA = re.compile(r"compra=(\d{6})(\d{2})(\d{5})(\d{4})")


def rotulo_da_compra(salva) -> str:
    """"Pregão 112/2026": como a compra é chamada no dia a dia. Do Compras.gov
    sai do código no link; dos outros portais, da modalidade e do sequencial."""

    if codigo := _CODIGO_DA_COMPRA.search(salva.link_plataforma or ""):
        _, modalidade, numero, ano = codigo.groups()
        nome = MODALIDADE_COMPRAS_GOV.get(modalidade, "Compra")
        return f"{nome} {int(numero)}/{ano}"
    nome = (salva.modalidade or "Compra").split(" - ")[0].strip()
    return f"{nome} {salva.sequencial_compra}/{salva.ano_compra}"


def _cotacao_de(salva):
    try:
        return salva.cotacao
    except OportunidadeSalva.cotacao.RelatedObjectDoesNotExist:
        return None


def _proposta_de(salva):
    try:
        return salva.proposta
    except OportunidadeSalva.proposta.RelatedObjectDoesNotExist:
        return None


def _participacao_de(salva):
    try:
        return salva.participacao
    except OportunidadeSalva.participacao.RelatedObjectDoesNotExist:
        return None


def avaliar(salva: OportunidadeSalva, hoje: dt.date) -> tuple[dict | None, Saida | None]:
    """O cartão da licitação na Torre, ou para onde ela saiu."""

    participacao = _participacao_de(salva)
    itens = list(salva.itens_participados.all())
    documentos = list(salva.documentos_financeiros.all())
    entregas = list(salva.entregas.all())
    prazo = salva.data_encerramento_proposta
    prazo_vencido = bool(prazo and prazo < hoje)

    etiquetas: list[Etiqueta] = []
    if participacao:
        if participacao.situacao_compra in SITUACOES_QUE_ENCERRAM:
            return None, Saida("encerradas", SITUACOES_QUE_ENCERRAM[participacao.situacao_compra])
        if participacao.convocacao_em_andamento:
            etiquetas.append(Etiqueta("alerta", "convocação em andamento"))
        if participacao.diligencia_em_andamento:
            etiquetas.append(Etiqueta("alerta", "diligência em andamento"))
        if participacao.situacao_compra == "SU":
            etiquetas.append(Etiqueta("info", "suspensa"))

    cartoes_itens = []
    etapa = None
    if itens:
        for item in itens:
            docs_do_item = [d for d in documentos if d.item_id in (None, item.pk)]
            entregas_do_item = [e for e in entregas if e.item_id in (None, item.pk)]
            resultado = etapa_do_item(item, docs_do_item, entregas_do_item, hoje)
            etiquetas.extend(resultado.etiquetas)
            valor = _valor_unitario(item)
            total = valor * item.quantidade if valor is not None and item.quantidade is not None else valor
            if total is not None:
                total = total.quantize(CENTAVO)
            cartoes_itens.append(
                {
                    "numero": item.numero_item,
                    "descricao": item.descricao,
                    "etapa": resultado.etapa,
                    "etapa_rotulo": ROTULO.get(resultado.etapa, ""),
                    "situacao": item.get_situacao_proposta_display() if item.situacao_proposta else "",
                    "classificacao": item.classificacao,
                    "perdendo": resultado.perdendo,
                    "perdido": resultado.perdido,
                    "quantidade": item.quantidade,
                    "valor_unitario": valor,
                    "valor_total": total,
                }
            )
            if resultado.etapa and (etapa is None or ORDEM[resultado.etapa] > ORDEM[etapa]):
                etapa = resultado.etapa
        if etapa is None:
            return None, Saida("encerradas", "Perdida")
    elif participacao and participacao.proposta_cadastrada is False and (
        participacao.fase_compra not in FASES_COMPRA_ANTES_DA_SESSAO or prazo_vencido
    ):
        return None, Saida("descartadas", "Sem proposta cadastrada")
    elif participacao and participacao.proposta_cadastrada:
        etapa = "disputa" if participacao.fase_compra == FASE_COMPRA_EM_DISPUTA else "cadastro_proposta"
    elif prazo_vencido:
        if not _cotacao_de(salva):
            return None, Saida("descartadas", "Prazo venceu sem cotação")
        if salva.plataforma_id == PLATAFORMA_COM_SENTINELA:
            # Até a Sentinela ler o Compras.gov.br não dá para saber se a
            # proposta foi cadastrada: espera aqui em vez de ir para Descartadas.
            etapa = "cadastro_proposta"
            etiquetas.append(Etiqueta("aviso", "confirmar com a Sentinela"))
        elif _proposta_de(salva):
            # Proposta gerada no fluxo antigo, em portal que a Sentinela não
            # lê: é sinal de que participou. Fica até alguém confirmar.
            etapa = "cadastro_proposta"
            etiquetas.append(Etiqueta("aviso", "confirmar participação"))
        else:
            return None, Saida("descartadas", "Prazo venceu com cotação")
    else:
        etapa = "cotacao" if _cotacao_de(salva) else "oportunidade"

    if etapa == "cadastro_proposta" and prazo and not prazo_vencido and (prazo - hoje).days <= 1:
        etiquetas.insert(0, Etiqueta("alerta", "proposta até hoje" if prazo == hoje else "proposta até amanhã"))

    ganhos = [
        c["valor_total"]
        for c in cartoes_itens
        if c["etapa"] and not c["perdendo"] and c["valor_total"] is not None
    ]
    cartao = {
        "id": salva.pk,
        "estagio": ESTAGIO_DA_ETAPA[etapa],
        "etapa": etapa,
        "etapa_rotulo": ROTULO[etapa],
        "uasg": salva.uasg,
        "compra": rotulo_da_compra(salva),
        "orgao_nome": salva.orgao_nome,
        "municipio": salva.municipio,
        "uf": salva.uf,
        "objeto": salva.objeto,
        "data_encerramento_proposta": prazo,
        "valor_total_estimado": salva.valor_total_estimado,
        "link_plataforma": salva.link_plataforma,
        "cotacao_id": cotacao.pk if (cotacao := _cotacao_de(salva)) else None,
        # Em Preparar o cartão abre os modais que já existem (visualizador da
        # oportunidade e Cotador), que precisam do registro inteiro.
        "salva": OportunidadeSalvaSerializer(salva).data if ESTAGIO_DA_ETAPA[etapa] == "preparar" else None,
        "itens": cartoes_itens,
        "valor_ganho": sum(ganhos, Decimal(0)) if ganhos else None,
        "etiquetas": [{"nivel": e.nivel, "texto": e.texto} for e in _sem_repetir(etiquetas)],
    }
    return cartao, None


def _sem_repetir(etiquetas: list[Etiqueta]) -> list[Etiqueta]:
    vistas: list[Etiqueta] = []
    for etiqueta in etiquetas:
        if etiqueta not in vistas:
            vistas.append(etiqueta)
    # Alerta primeiro, depois aviso, depois informação.
    peso = {"alerta": 0, "aviso": 1, "info": 2}
    return sorted(vistas, key=lambda e: peso.get(e.nivel, 3))


def _urgencia(cartao: dict) -> tuple:
    """Quem precisa de atenção primeiro: alerta, aviso, depois o prazo mais
    curto. Sem prazo vai para o fim."""

    niveis = {e["nivel"] for e in cartao["etiquetas"]}
    grau = 0 if "alerta" in niveis else 1 if "aviso" in niveis else 2
    return (grau, cartao["data_encerramento_proposta"] or dt.date.max, cartao["id"])


def montar_torre(hoje: dt.date | None = None) -> dict:
    """Os 4 estágios com as etapas, os cartões e quantas licitações saíram."""

    hoje = hoje or timezone.localdate()
    salvas = (
        OportunidadeSalva.objects.ativas()
        .select_related("cotacao", "participacao", "proposta")
        .prefetch_related("itens_participados", "documentos_financeiros", "entregas")
    )

    por_estagio: dict[str, list[dict]] = {chave: [] for chave, _, _ in ESTAGIOS}
    saidas = {"encerradas": 0, "descartadas": 0}
    for salva in salvas:
        cartao, saida = avaliar(salva, hoje)
        if saida:
            saidas[saida.para] += 1
            continue
        por_estagio[cartao["estagio"]].append(cartao)

    estagios = []
    for chave, rotulo, etapas in ESTAGIOS:
        cartoes = sorted(por_estagio[chave], key=_urgencia)
        estagios.append(
            {
                "chave": chave,
                "rotulo": rotulo,
                "total": len(cartoes),
                "etapas": [
                    {
                        "chave": etapa,
                        "rotulo": rotulo_etapa,
                        "total": sum(1 for c in cartoes if c["etapa"] == etapa),
                    }
                    for etapa, rotulo_etapa in etapas
                ],
                "cartoes": cartoes,
            }
        )
    return {"hoje": hoje, "estagios": estagios, "saidas": saidas}
