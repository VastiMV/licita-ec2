"""Sincronia diária com o Portal da Transparência: empenho, liquidação e
pagamento dos órgãos federais, sem ninguém ligar para perguntar.

Para cada CNPJ ativo em Cadastros › Empresas, o Portal devolve os documentos
de despesa em que a empresa é a favorecida (ano atual e anterior, as três
fases). Cada um vira `DocumentoFinanceiro` com fonte "transparencia" e é
**ligado à licitação**, da regra mais segura para a menos segura:

1. **processo** — o número do processo do documento (ou citado na
   observação, como costuma vir no pagamento) é o da licitação. Iguais
   quando os dígitos são os mesmos ("02001.015536/2024-21" =
   "02001015536202421") **ou** quando cada pedaço entre os símbolos é o mesmo
   sem os zeros à esquerda ("00054-00061297/2026-38" do PNCP =
   "054-00061297/2026-38" do Portal — PMDF 56/2026, GEN-97, 18/11/2026);
2. **unidade** — a UG do documento é a UASG de **uma única** licitação ganha.

Sem ligação, o documento fica guardado "sem licitação" para alguém escolher
(`GET documentos-financeiros/sem-licitacao/`). Uma ligação feita à mão nunca é
desfeita pela sincronia.

Cada documento novo vira **aviso no sino** (e no Telegram): "ligou sozinho"
com a licitação, ou "sem licitação" para ligar à mão; e de novo quando um
"sem licitação" passa a ligar sozinho (GEN-97, 18/11/2026). O aviso diz o
**órgão pagador**, que pode não ser a UASG da compra (PMDF: o FCDF).

Estados e prefeituras não estão no Portal (cada um tem o seu): para eles o
empenho continua manual. Agendada todo dia às 8h10, depois da do PNCP
(`tasks.sincronizar_transparencia`); também roda à mão com
`manage.py sincronizar_transparencia`.
"""

from __future__ import annotations

import datetime as dt
import logging
import re

from django.db.models import Q
from django.utils import timezone

from apps.empresas.models import Empresa
from apps.integracoes.clients.transparencia import (
    FASE_EMPENHO,
    FASE_LIQUIDACAO,
    FASE_PAGAMENTO,
    PortalTransparenciaClient,
    TransparenciaError,
    data_brasileira,
    valor_brasileiro,
)
from apps.notificacoes.servico import avisar
from apps.propostas.documento import brl
from config.settings.environment import env

from .models import DocumentoFinanceiro, Fonte, ItemParticipado, OportunidadeSalva
from .torre import rotulo_da_compra

logger = logging.getLogger(__name__)

TIPO_DA_FASE = {
    FASE_EMPENHO: DocumentoFinanceiro.Tipo.EMPENHO,
    FASE_LIQUIDACAO: DocumentoFinanceiro.Tipo.LIQUIDACAO,
    FASE_PAGAMENTO: DocumentoFinanceiro.Tipo.PAGAMENTO,
}
PROCESSO_NA_OBSERVACAO = re.compile(r"PROCESSO\s*(?:N[º°O.]*)?\s*:?\s*([\d./-]{8,})", re.IGNORECASE)


def _digitos(texto: str | None) -> str:
    return re.sub(r"\D", "", texto or "")


def _pedacos(texto: str | None) -> list[str]:
    """"00054-00061297/2026-38" → ["54", "61297", "2026", "38"]."""

    return [pedaco.lstrip("0") or "0" for pedaco in re.findall(r"\d+", texto or "")]


def mesmo_processo(um: str | None, outro: str | None) -> bool:
    """O número do processo não tem tamanho fixo (cada órgão e cada sistema
    tem o seu) e o SIAFI corta zeros à esquerda que o PNCP mantém. Iguais pelos
    dígitos ou, havendo símbolos nos dois, pedaço a pedaço sem esses zeros."""

    digitos_um, digitos_outro = _digitos(um), _digitos(outro)
    if not digitos_um or not digitos_outro:
        return False
    if digitos_um == digitos_outro:
        return True
    pedacos_um = _pedacos(um)
    return len(pedacos_um) > 1 and pedacos_um == _pedacos(outro)


def _processo_do_documento(registro: dict) -> str:
    """O processo como veio (com os símbolos): eles separam os pedaços."""

    processo = (registro.get("numeroProcesso") or "").strip()
    if _digitos(processo):
        return processo
    achado = PROCESSO_NA_OBSERVACAO.search(registro.get("observacao") or "")
    return achado.group(1).strip(" .-/") if achado else ""


def _licitacoes_ganhas() -> list[OportunidadeSalva]:
    """As licitações em que a empresa ganhou (ou está ganhando) algum item:
    só elas recebem empenho."""

    ganhou = Q(vencedor_e_a_empresa=True) | Q(situacao_proposta__in=["3", "4", "6"])
    ids = ItemParticipado.objects.filter(ganhou).values("oportunidade_id")
    return list(OportunidadeSalva.objects.ativas().filter(pk__in=ids))


def _ligar(registro: dict, candidatas: list[OportunidadeSalva]) -> tuple[OportunidadeSalva | None, str]:
    processo = _processo_do_documento(registro)
    if processo:
        for salva in candidatas:
            if mesmo_processo(salva.numero_processo, processo):
                return salva, "processo"
    mesma_unidade = [s for s in candidatas if s.uasg and s.uasg == str(registro.get("codigoUg") or "")]
    if len(mesma_unidade) == 1:
        return mesma_unidade[0], "unidade"
    return None, ""


def _gravar(registro: dict, fase: int, candidatas: list[OportunidadeSalva], resumo: dict) -> None:
    numero = registro.get("documento") or registro.get("documentoResumido")
    if not numero:
        return
    existente = DocumentoFinanceiro.objects.filter(
        fonte=Fonte.TRANSPARENCIA, tipo=TIPO_DA_FASE[fase], numero=numero
    ).first()
    salva, ligado_por = (existente.oportunidade, existente.dados.get("ligado_por", "manual")) if (
        existente and existente.oportunidade_id
    ) else _ligar(registro, candidatas)

    dados = {
        "documento_resumido": registro.get("documentoResumido"),
        "observacao": registro.get("observacao"),
        "codigo_ug": registro.get("codigoUg"),
        "ug": registro.get("ug"),
        "orgao": registro.get("orgao"),
        "numero_processo": registro.get("numeroProcesso"),
        "ligado_por": ligado_por,
    }
    doc, novo = DocumentoFinanceiro.objects.update_or_create(
        fonte=Fonte.TRANSPARENCIA,
        tipo=TIPO_DA_FASE[fase],
        numero=numero,
        defaults={
            "oportunidade": salva,
            "data": data_brasileira(registro.get("data")),
            "valor": valor_brasileiro(registro.get("valor")),
            "dados": dados,
        },
    )
    resumo["documentos"] += 1
    resumo["ligados" if salva else "sem_licitacao"] += 1
    if novo or (salva and not (existente and existente.oportunidade_id)):
        _avisar(doc)


def _avisar(doc: DocumentoFinanceiro) -> None:
    """Um aviso por documento e por situação ("ligado", "sem licitação"): a
    `chave` impede repetir a cada rodada."""

    numero = doc.dados.get("documento_resumido") or doc.numero
    partes = [f"{doc.get_tipo_display()} {numero}", brl(doc.valor)]
    if doc.orgao_pagador:
        partes.append(f"pago por: {doc.orgao_pagador}")
    if doc.oportunidade_id:
        avisar(
            "financeiro",
            f"{doc.get_tipo_display()} · {rotulo_da_compra(doc.oportunidade)}",
            texto=" · ".join(partes) + ". Veio do Portal da Transparência.",
            oportunidade=doc.oportunidade,
            nivel="info",
            chave=f"financeiro:{doc.pk}:ligado",
        )
        return
    processo = doc.dados.get("numero_processo") or "sem número"
    avisar(
        "financeiro",
        f"{doc.get_tipo_display()} sem licitação · {numero}",
        texto=(
            " · ".join(partes) + f" · processo {processo}. Veio do Portal da Transparência e o "
            "Licita não achou a licitação: ligue à mão."
        ),
        nivel="aviso",
        chave=f"financeiro:{doc.pk}:sem_licitacao",
    )


def sincronizar_transparencia(hoje: dt.date | None = None, cliente=None) -> dict:
    """Lê empenhos, liquidações e pagamentos de cada CNPJ ativo. Devolve o
    que fez; um erro do Portal fica no resumo, não derruba a tarefa."""

    hoje = hoje or timezone.localdate()
    resumo: dict = {"documentos": 0, "ligados": 0, "sem_licitacao": 0, "sem_chave": False, "erro": ""}
    if cliente is None and not env.portal_transparencia_chave:
        resumo["sem_chave"] = True
        logger.warning("Portal da Transparência: PORTAL_TRANSPARENCIA_CHAVE não configurada; sincronia pulada.")
        return resumo

    cnpjs = sorted(set(Empresa.objects.filter(ativa=True).values_list("cnpj", flat=True)))
    candidatas = _licitacoes_ganhas()
    proprio = cliente is None
    cliente = cliente or PortalTransparenciaClient()
    try:
        for cnpj in cnpjs:
            for ano in (hoje.year - 1, hoje.year):
                for fase in TIPO_DA_FASE:
                    for registro in cliente.documentos_do_favorecido(cnpj, fase, ano):
                        _gravar(registro, fase, candidatas, resumo)
    except TransparenciaError as exc:
        resumo["erro"] = str(exc)
        logger.error("Portal da Transparência: %s", exc)
    finally:
        if proprio:
            cliente.close()
    return resumo
