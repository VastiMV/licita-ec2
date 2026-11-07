"""Sincronia diária com o Portal da Transparência: empenho, liquidação e
pagamento dos órgãos federais, sem ninguém ligar para perguntar.

Para cada CNPJ ativo em Cadastros › Empresas, o Portal devolve os documentos
de despesa em que a empresa é a favorecida (ano atual e anterior, as três
fases). Cada um vira `DocumentoFinanceiro` com fonte "transparencia" e é
**ligado à licitação**, da regra mais segura para a menos segura:

1. **processo** — o número do processo do documento (ou citado na
   observação, como costuma vir no pagamento) é o da licitação, comparando
   só os dígitos ("02001.015536/2024-21" = "02001015536202421");
2. **unidade** — a UG do documento é a UASG de **uma única** licitação ganha.

Sem ligação, o documento fica guardado "sem licitação" para alguém escolher
(`GET documentos-financeiros/sem-licitacao/`). Uma ligação feita à mão nunca é
desfeita pela sincronia.

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
from config.settings.environment import env

from .models import DocumentoFinanceiro, Fonte, ItemParticipado, OportunidadeSalva

logger = logging.getLogger(__name__)

TIPO_DA_FASE = {
    FASE_EMPENHO: DocumentoFinanceiro.Tipo.EMPENHO,
    FASE_LIQUIDACAO: DocumentoFinanceiro.Tipo.LIQUIDACAO,
    FASE_PAGAMENTO: DocumentoFinanceiro.Tipo.PAGAMENTO,
}
PROCESSO_NA_OBSERVACAO = re.compile(r"PROCESSO\s*(?:N[º°O.]*)?\s*:?\s*([\d./-]{8,})", re.IGNORECASE)


def _digitos(texto: str | None) -> str:
    return re.sub(r"\D", "", texto or "")


def _processo_do_documento(registro: dict) -> str:
    processo = _digitos(registro.get("numeroProcesso"))
    if processo:
        return processo
    achado = PROCESSO_NA_OBSERVACAO.search(registro.get("observacao") or "")
    return _digitos(achado.group(1)) if achado else ""


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
            if _digitos(salva.numero_processo) == processo:
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
    DocumentoFinanceiro.objects.update_or_create(
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
