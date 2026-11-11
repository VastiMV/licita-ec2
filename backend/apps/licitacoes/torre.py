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
            # Proposta com preço lançado no Compras.gov, sessão ainda fechada
            # (10/11/2026): não há mais o que fazer em Preparar, mas também não
            # é Disputa — Disputa é sessão aberta, lance acontecendo agora.
            ("aguardando_sessao", "Aguardando sessão"),
            ("disputa", "Disputa"),
            ("aguardando_julgamento", "Aguardando julgamento"),
            ("julgado_habilitado", "Aceita e habilitada"),
            ("aguardando_adjudicacao", "Habilitada (aguardando adjudicação)"),
        ],
    ),
    # Homologado abre Contratar (pedido do Carlinhos, 08/11/2026): ganhou,
    # agora é esperar contrato ou empenho. A ordem das etapas não muda.
    (
        "contratar",
        "Contratar",
        [("homologado", "Homologado"), ("contrato", "Contrato"), ("empenho", "Empenho / Ordem de Fornecimento")],
    ),
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
CHAVE_DA_SITUACAO = {"RE": "revogada", "AN": "anulada", "FR": "fracassada", "DE": "deserta"}
SUSPENSA = "SU"
# Situação da compra no PNCP (conferida 1x por dia pelo servidor).
PNCP_SUSPENSA = "suspensa"
PNCP_ENCERRADA = {"revogada": "Revogada (PNCP)", "anulada": "Anulada (PNCP)"}


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

    # Convocação, pedido de desconto ou recurso em aberto: o item está vivo,
    # mesmo que antes tenha sido dado como perdido (09/11/2026).
    if not chamado_de_volta(item):
        if item.vencedor_e_a_empresa is False:
            return EtapaDoItem(None, perdido="homologado para outro fornecedor")
        if item.situacao_proposta in PROPOSTA_DESCLASSIFICADA:
            return EtapaDoItem(None, perdido="proposta desclassificada")
        if item.situacao_proposta == FORNECEDOR_INABILITADO:
            return EtapaDoItem(None, perdido="fornecedor inabilitado")
        if item.situacao_proposta not in JA_JULGADA and primeiro_ja_habilitado(item):
            # Na frente dele já aceitaram/habilitaram outra empresa: na prática
            # perdeu; só volta por recurso ou se o outro não assinar (vigia).
            return EtapaDoItem(None, perdido="1º já habilitado")

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
            # Recurso é vermelho (pedido da operação, 08/11/2026).
            etiqueta = (
                Etiqueta("alerta", f"recurso até {item.recurso_ate:%d/%m}")
                if item.recurso_ate
                else Etiqueta("alerta", "em fase de recurso")
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
    if item.valor_proposta_inicial:
        # Preço lançado no Compras.gov e a sessão não abriu: a proposta está
        # feita, com ou sem cotação no Licita (decisão de 10/11/2026: o
        # Compras.gov é o que vale para a disputa).
        return EtapaDoItem("aguardando_sessao")
    return EtapaDoItem("cadastro_proposta")


# SituacaoRecursalEnum: P procede, N não procede, M mantida (não procede),
# R revertida (passou a proceder).
RECURSO_INDEFERIDO = {"N", "M"}
RECURSO_PROCEDENTE = {"P", "R"}


PERDEU_A_VEZ = {"1", "2", "9", "5"}  # desclassificada (1, 2, 9) ou inabilitado (5)
FICOU_COM_O_ITEM = {"6", "4", "3"}  # adjudicada, habilitado, aceita


def proposta_vencedora(propostas: list):
    """Num item homologado: a adjudicada; senão a melhor habilitada/aceita;
    senão a mais bem classificada que não caiu."""

    def posicao(p):
        return p.classificacao or 10**6

    for situacoes in ({"6"}, FICOU_COM_O_ITEM):
        candidatas = sorted((p for p in propostas if p.situacao in situacoes), key=posicao)
        if candidatas:
            return candidatas[0]
    restantes = sorted((p for p in propostas if p.situacao not in PERDEU_A_VEZ), key=posicao)
    return restantes[0] if restantes else None


def posicao_efetiva(item) -> int | None:
    """Em que lugar da fila a empresa está **de verdade**: a posição menos
    quem, na frente dela, já caiu (desclassificado ou inabilitado). Sem a
    lista de propostas (`PropostaDoItem`), vale a posição que veio."""

    if not item.classificacao:
        return None
    propostas = list(item.propostas.all())
    if not propostas:
        return item.classificacao
    na_frente = [
        p
        for p in propostas
        if not p.da_empresa and p.classificacao and p.classificacao < item.classificacao
    ]
    caidas = sum(1 for p in na_frente if p.situacao in PROPOSTA_DESCLASSIFICADA | {FORNECEDOR_INABILITADO})
    return item.classificacao - caidas


JA_JULGADA = {"3", "4", "6"}  # aceita, habilitado, adjudicada


def _vivas_na_frente(item) -> list | None:
    """As propostas de outras empresas na frente da dele que não caíram.
    `None` = a lista de propostas ainda não foi lida."""

    if not item.classificacao:
        return None
    propostas = list(item.propostas.all())
    if not propostas:
        return None
    return [
        p
        for p in propostas
        if not p.da_empresa
        and p.classificacao
        and p.classificacao < item.classificacao
        and p.situacao not in PERDEU_A_VEZ
    ]


def primeiro_ja_habilitado(item) -> bool:
    """Alguém na frente dele já foi aceito/habilitado/adjudicado."""

    vivas = _vivas_na_frente(item)
    return bool(vivas) and any(p.situacao in JA_JULGADA for p in vivas)


def chamado_de_volta(item) -> bool:
    """Convocação, pedido de desconto ou recurso que ainda pede resposta: o
    item volta para a Torre, em vermelho, de onde estiver."""

    if item.anexo_solicitado == "S" or (item.negociacao and item.negociacao != "E"):
        return True
    if getattr(item, "recursos", None):
        if item.decisao_recurso in RECURSO_PROCEDENTE:
            return True
        if not item.decisao_recurso:
            return True  # aguardando decisão
    return False


def sinal_do_item(item, etapa: EtapaDoItem) -> str:
    """👍 "ganhando" (1º de verdade, ou ganhou) · 🟠 "proximo" (só o próximo
    de verdade: na frente dele só sobrou quem está sendo analisado agora) ·
    👎 "perdendo" (atrás disso, ou perdeu) · "" (sem posição).
    Quem caiu na frente (desclassificado/inabilitado) não conta."""

    if etapa.etapa is None:
        return "perdendo"
    if item.vencedor_e_a_empresa or ORDEM[etapa.etapa] >= ORDEM["homologado"]:
        return "ganhando"
    if item.situacao_proposta in JA_JULGADA:
        return "ganhando"
    vivas = _vivas_na_frente(item)
    if vivas is None:
        if not item.classificacao:
            return ""
        return "ganhando" if item.classificacao <= 1 else "proximo" if item.classificacao == 2 else "perdendo"
    if not vivas:
        return "ganhando"
    return "proximo" if len(vivas) == 1 else "perdendo"


def _avisos_do_item(item, agora: dt.datetime | None = None) -> list[Etiqueta]:
    """O que pede ação agora, item a item (Sentinela). Tudo que pede
    resposta da empresa é vermelho: convocação, pedido de desconto, recurso,
    diligência."""

    agora = agora or timezone.now()
    n = item.numero_item
    avisos = []
    if item.negociacao and item.negociacao != "E":
        avisos.append(Etiqueta("alerta", f"pedido de desconto · item {n}"))
    if item.anexo_solicitado == "S":
        avisos.append(Etiqueta("alerta", f"convocação: enviar anexo · item {n}"))
    if item.diligencias_abertas:
        avisos.append(Etiqueta("alerta", f"diligência · item {n}"))
    if item.recursos:
        nomes = item.recursos[0].get("nome") or "outra empresa"
        if len(item.recursos) > 1:
            nomes += f" e mais {len(item.recursos) - 1}"
        if item.decisao_recurso in RECURSO_INDEFERIDO:
            avisos.append(Etiqueta("info", f"recurso indeferido · item {n}"))
        elif item.decisao_recurso in RECURSO_PROCEDENTE:
            avisos.append(Etiqueta("alerta", f"recurso procedente · item {n}"))
        elif item.prazo_contrarrazao and item.prazo_contrarrazao >= agora:
            prazo = timezone.localtime(item.prazo_contrarrazao)
            avisos.append(
                Etiqueta("alerta", f"recurso de {_curto(nomes)} · item {n} · contrarrazões até {prazo:%d/%m %H:%M}")
            )
        else:
            avisos.append(Etiqueta("alerta", f"recurso de {_curto(nomes)} · item {n} · aguardando decisão"))
    return avisos


def _curto(nome: str) -> str:
    """"BRAVA SUL COMERCIO DE EQUIPAMENTOS…" → "Brava Sul"."""

    palavras = [p for p in nome.replace(",", " ").split() if p]
    return " ".join(palavras[:2]).title() if palavras else nome


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
    motivo: str  # o texto ("Perdida")
    chave: str = ""  # a chave da lista (`encerradas.MOTIVOS` / `MOTIVOS_DESCARTE`)
    data: dt.date | None = None  # quando saiu


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


def link_do_fornecedor(link: str) -> str:
    """Na Torre o "Abrir" vai para a página **do fornecedor** (logada), que
    tem "Itens em que estou participando", a proposta da empresa — e é onde a
    Sentinela lê. A página pública (`/public/compras/`) não tem nada disso
    (pedido da operação, 08/11/2026). A busca continua com o link público."""

    return (link or "").replace(
        "/comprasnet-web/public/compras/acompanhamento-compra",
        "/comprasnet-web/seguro/fornecedor/acompanhamento-compra",
    )


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


def _data(momento) -> dt.date | None:
    return timezone.localdate(momento) if momento else None


def avaliar(salva: OportunidadeSalva, hoje: dt.date) -> tuple[dict | None, Saida | None]:
    """O cartão da licitação na Torre, ou para onde ela saiu (com o motivo e
    a data). É a **única** regra: as listas de Encerradas e Descartadas e os
    números do menu saem daqui (`encerradas.classificar`)."""

    participacao = _participacao_de(salva)
    itens = list(salva.itens_participados.all())
    documentos = list(salva.documentos_financeiros.all())
    entregas = list(salva.entregas.all())
    prazo = salva.data_encerramento_proposta
    prazo_vencido = bool(prazo and prazo < hoje)
    cotacao = _cotacao_de(salva)

    etiquetas: list[Etiqueta] = []
    suspensa = salva.situacao_pncp == PNCP_SUSPENSA
    if participacao:
        if participacao.situacao_compra in SITUACOES_QUE_ENCERRAM:
            return None, Saida(
                "encerradas",
                SITUACOES_QUE_ENCERRAM[participacao.situacao_compra],
                CHAVE_DA_SITUACAO[participacao.situacao_compra],
                _data(participacao.atualizada_em),
            )
        if participacao.convocacao_em_andamento:
            etiquetas.append(Etiqueta("alerta", "convocação em andamento"))
        if participacao.diligencia_em_andamento:
            etiquetas.append(Etiqueta("alerta", "diligência em andamento"))
        suspensa = suspensa or participacao.situacao_compra == SUSPENSA
    if salva.situacao_pncp in PNCP_ENCERRADA:
        etiquetas.append(Etiqueta("alerta", PNCP_ENCERRADA[salva.situacao_pncp]))
    if suspensa:
        etiquetas.append(Etiqueta("aviso", "Compra suspensa"))
    # Disputa agendada sem data (Butantan, 9/2026): o prazo passou, a sessão
    # ainda não tem dia. A data nova vem pela Sentinela ou pelo PNCP.
    sem_prazo = bool(
        participacao
        and participacao.fase_compra in FASES_COMPRA_ANTES_DA_SESSAO
        and participacao.sessao_abre_em is None
        and prazo_vencido
        and not suspensa
    )
    if sem_prazo:
        etiquetas.append(Etiqueta("aviso", "Sem prazo definido"))

    cartoes_itens = []
    etapa = None
    if itens:
        for item in itens:
            docs_do_item = [d for d in documentos if d.item_id in (None, item.pk)]
            entregas_do_item = [e for e in entregas if e.item_id in (None, item.pk)]
            resultado = etapa_do_item(item, docs_do_item, entregas_do_item, hoje)
            etiquetas.extend(resultado.etiquetas)
            if resultado.etapa:
                etiquetas.extend(_avisos_do_item(item))
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
                    "sinal": sinal_do_item(item, resultado),
                    "quantidade": item.quantidade,
                    "valor_unitario": valor,
                    "valor_total": total,
                }
            )
            if resultado.etapa and (etapa is None or ORDEM[resultado.etapa] > ORDEM[etapa]):
                etapa = resultado.etapa
        if etapa is None:
            ultima = max((i.atualizado_em for i in itens if i.atualizado_em), default=None)
            return None, Saida("encerradas", "Perdida", "perdida", _data(ultima) or prazo)
    elif participacao and participacao.proposta_cadastrada is False and (
        participacao.fase_compra not in FASES_COMPRA_ANTES_DA_SESSAO or prazo_vencido
    ) and not (suspensa or sem_prazo):
        return None, Saida(
            "descartadas", "Sem proposta cadastrada", "sem_proposta", _data(participacao.atualizada_em)
        )
    elif participacao and participacao.proposta_cadastrada:
        etapa = "disputa" if participacao.fase_compra == FASE_COMPRA_EM_DISPUTA else "cadastro_proposta"
    elif suspensa or sem_prazo:
        # Suspensa ou sem data (09/11/2026): fica em Preparar esperando a data
        # nova; nunca sai sozinha por prazo.
        etapa = "cotacao" if cotacao else "oportunidade"
    elif participacao and not cotacao and (
        prazo_vencido or participacao.fase_compra not in FASES_COMPRA_ANTES_DA_SESSAO
    ):
        # Está em "Minhas participações", o prazo passou e não há cotação: ele
        # só quer ver o resultado ("xeretar", 09/11/2026). Vai para Encerradas
        # com relatório; se a vigia achar proposta dele, volta para a Torre.
        return None, Saida("encerradas", "Acompanhando o resultado", "acompanhando", prazo)
    elif participacao and participacao.fase_compra not in FASES_COMPRA_ANTES_DA_SESSAO:
        # Com cotação, já depois da sessão, sem os itens lidos: não dá para
        # saber se há proposta. Fica no quadro pedindo a leitura.
        etapa = "disputa" if participacao.fase_compra == FASE_COMPRA_EM_DISPUTA else "aguardando_julgamento"
        etiquetas.append(Etiqueta("aviso", "abrir a compra no Compras.gov"))
    elif prazo_vencido:
        if not cotacao:
            return None, Saida("descartadas", "Prazo venceu sem cotação", "prazo_oportunidade", prazo)
        # Compras.gov.br sem nenhuma participação lida, prazo vencido: cotou e
        # não participou (decisão de 10/11/2026, Guarulhos 461/2026). Antes
        # ficava em Cadastro de proposta "confirmar com a Sentinela" e, sem
        # proposta, a confirmação nunca chegava. Descartadas é calculado: se a
        # Sentinela achar participação depois, a compra volta sozinha.
        if salva.plataforma_id != PLATAFORMA_COM_SENTINELA and _proposta_de(salva):
            # Proposta gerada no fluxo antigo, em portal que a Sentinela não
            # lê: é sinal de que participou. Fica até alguém confirmar.
            etapa = "cadastro_proposta"
            etiquetas.append(Etiqueta("aviso", "confirmar participação"))
        else:
            return None, Saida("descartadas", "Prazo venceu com cotação", "prazo_cotacao", prazo)
    else:
        etapa = "cotacao" if cotacao else "oportunidade"

    if ESTAGIO_DA_ETAPA[etapa] == "preparar" and salva.favorita_no_compras is False:
        # Ele tirou dos favoritos no Compras.gov (09/11/2026): o Licita avisa,
        # quem decide descartar é ele (lixeira).
        etiquetas.append(Etiqueta("aviso", "fora dos favoritos no Compras.gov"))

    if etapa == "aguardando_sessao":
        if participacao and participacao.sessao_abre_em:
            abre = timezone.localtime(participacao.sessao_abre_em)
            etiquetas.insert(0, Etiqueta("info", f"sessão {abre:%d/%m %H:%M}"))
        if cotacao is None:
            etiquetas.append(Etiqueta("aviso", "sem cotação no Licita"))

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
        "link_plataforma": link_do_fornecedor(salva.link_plataforma),
        "cotacao_id": cotacao.pk if cotacao else None,
        # Para o cabeçalho do modal Processo ("Valor cotado").
        "valor_cotado": float(cotacao.valor_cotado) if cotacao else None,
        # O registro inteiro, para os modais que já existem: em Preparar, o
        # visualizador da oportunidade e o Cotador; dali em diante, o modal
        # Processo (GEN-53/64, 11/11/2026: o cartão abria o Compras.gov, que
        # sem a aba logada dava página inválida).
        "salva": OportunidadeSalvaSerializer(salva).data,
        "itens": cartoes_itens,
        "valor_ganho": sum(ganhos, Decimal(0)) if ganhos else None,
        # "ganhando 1 de 8": dos itens com posição conhecida.
        "itens_ganhando": sum(1 for c in cartoes_itens if c["sinal"] == "ganhando"),
        "itens_com_posicao": sum(1 for c in cartoes_itens if c["sinal"]),
        "itens_proximos": sum(1 for c in cartoes_itens if c["sinal"] == "proximo"),
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
        .prefetch_related("itens_participados__propostas", "documentos_financeiros", "entregas")
    )

    por_estagio: dict[str, list[dict]] = {chave: [] for chave, _, _ in ESTAGIOS}
    for salva in salvas:
        cartao, saida = avaliar(salva, hoje)
        if saida:
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
    from .encerradas import contar

    # Os números das saídas são os das listas (a mesma regra, `classificar`).
    return {"hoje": hoje, "estagios": estagios, "saidas": contar(hoje)}
