"""A conferência diária do servidor (09/11/2026), seg–sex de manhã — não
depende do computador do Carlinhos nem da Sentinela:

1. **Data e situação no PNCP** das licitações em Preparar: o órgão adiou,
   suspendeu, revogou ou anulou? Atualiza a data (com histórico e sino) e a
   situação ("Compra suspensa"; revogada/anulada em vermelho).
2. **Itens das compras que ele só acompanha** ("xeretar"): a lista de itens
   vem do PNCP; a Sentinela lê as propostas de cada um, 1x por dia.
3. **Fim da vigia** de quem perdeu: quando a ata de registro de preços do
   item aparece assinada com **outra** empresa (Dados Abertos do
   Compras.gov.br, por UASG). Contrato comum (sem ata) não aparece nessa
   fonte: para esses, vale o limite de 180 dias (`sentinela.ronda`).
"""

from __future__ import annotations

import datetime as dt
import logging
import re

from django.utils import timezone

from apps.empresas.models import Empresa
from apps.integracoes.clients.compras_gov import ComprasGovClient
from apps.integracoes.clients.pncp import PncpClient

from .models import ItemAcompanhado, ItemParticipado, OportunidadeSalva
from .torre import ESTAGIO_DA_ETAPA, avaliar, etapa_do_item

logger = logging.getLogger(__name__)

SITUACAO_PNCP = {2: "revogada", 3: "anulada", 4: "suspensa"}
CODIGO = re.compile(r"compra=(\d{6})\d{2}\d{5}\d{4}")
CODIGO_INTEIRO = re.compile(r"compra=(\d{17})")


def _salvas():
    return (
        OportunidadeSalva.objects.ativas()
        .select_related("cotacao", "participacao", "proposta")
        .prefetch_related("itens_participados__propostas", "documentos_financeiros", "entregas")
    )


def conferir(hoje: dt.date | None = None, pncp=None, compras=None) -> dict[str, int]:
    from apps.sentinela.ingestao import avisar_situacao, registrar_data_alterada

    hoje = hoje or timezone.localdate()
    pncp = pncp or PncpClient()
    compras = compras or ComprasGovClient()
    resumo = {"conferidas": 0, "datas": 0, "situacoes": 0, "itens_acompanhados": 0, "vigias_encerradas": 0, "falhas": 0}

    for salva in _salvas():
        cartao, saida = avaliar(salva, hoje)
        em_preparar = cartao is not None and ESTAGIO_DA_ETAPA[cartao["etapa"]] == "preparar"
        acompanhando = saida is not None and saida.chave == "acompanhando"
        if not (em_preparar or acompanhando) or not (salva.cnpj_orgao and salva.ano_compra and salva.sequencial_compra):
            continue
        try:
            if em_preparar:
                detalhe = pncp.detalhar_compra(
                    cnpj=salva.cnpj_orgao, ano=salva.ano_compra, sequencial=salva.sequencial_compra
                )
                resumo["conferidas"] += 1
                fim = detalhe.get("data_encerramento_proposta")
                fim = dt.date.fromisoformat(fim) if fim else None
                if fim and fim != salva.data_encerramento_proposta:
                    anterior = salva.data_encerramento_proposta
                    salva.data_encerramento_proposta = fim
                    salva.save(update_fields=["data_encerramento_proposta"])
                    if anterior:
                        registrar_data_alterada(salva, "prazo da proposta", anterior, fim)
                        resumo["datas"] += 1
                situacao = SITUACAO_PNCP.get(detalhe.get("situacao_id"), "")
                if situacao != salva.situacao_pncp:
                    if situacao:
                        avisar_situacao(
                            salva, f"Compra {situacao}", "aviso" if situacao == "suspensa" else "alerta"
                        )
                        resumo["situacoes"] += 1
                    salva.situacao_pncp = situacao
                salva.pncp_conferido_em = timezone.now()
                salva.save(update_fields=["situacao_pncp", "pncp_conferido_em"])
            elif acompanhando and not salva.itens_acompanhados.exists():
                for item in pncp.listar_itens(
                    cnpj=salva.cnpj_orgao, ano=salva.ano_compra, sequencial=salva.sequencial_compra
                ):
                    numero = str(item.get("numero_item") or "").strip()
                    if not numero:
                        continue
                    _, criado = ItemAcompanhado.objects.get_or_create(
                        oportunidade=salva,
                        numero_item=numero,
                        defaults={
                            "descricao": item.get("descricao_resumida") or "",
                            "quantidade": item.get("quantidade"),
                        },
                    )
                    resumo["itens_acompanhados"] += int(criado)
        except Exception:  # noqa: BLE001 — uma compra com problema não para as outras
            resumo["falhas"] += 1
            logger.exception("Conferência diária: falha na salva %s", salva.pk)

    resumo["vigias_encerradas"] = _encerrar_vigias(hoje, compras)
    return resumo


def _encerrar_vigias(hoje: dt.date, compras) -> int:
    """Itens perdidos cuja ata saiu assinada com outra empresa: a vigia acaba."""

    cnpjs = set(Empresa.objects.filter(ativa=True).values_list("cnpj", flat=True))
    por_unidade: dict[str, list[ItemParticipado]] = {}
    vigiados = (
        ItemParticipado.objects.filter(vigia_encerrada_em__isnull=True, oportunidade__link_plataforma__contains="compra=")
        .select_related("oportunidade")
        .prefetch_related("propostas")
    )
    for item in vigiados:
        if etapa_do_item(item, [], [], hoje).etapa is not None:
            continue  # vivo: nada a encerrar
        if achado := CODIGO.search(item.oportunidade.link_plataforma or ""):
            por_unidade.setdefault(achado.group(1), []).append(item)

    encerradas = 0
    inicio = (hoje - dt.timedelta(days=200)).isoformat()
    for unidade, itens in por_unidade.items():
        try:
            atas = compras.itens_de_ata_da_unidade(unidade, inicio, hoje.isoformat())
        except Exception:  # noqa: BLE001
            logger.exception("Conferência diária: falha ao ler atas da UASG %s", unidade)
            continue
        for item in itens:
            codigo = CODIGO_INTEIRO.search(item.oportunidade.link_plataforma).group(1)
            for ata in atas:
                mesma_compra = str(ata.get("idCompra") or "") == codigo
                mesmo_item = _numero(ata.get("numeroItem")) == _numero(item.numero_item)
                if mesma_compra and mesmo_item and str(ata.get("niFornecedor") or "") not in cnpjs:
                    quem = ata.get("nomeRazaoSocialFornecedor") or "outra empresa"
                    quando = str(ata.get("dataAssinatura") or "")[:10]
                    ItemParticipado.objects.filter(pk=item.pk).update(
                        vigia_encerrada_em=timezone.now(),
                        vigia_motivo=f"ata assinada com {quem[:60]} em {quando}"[:120],
                    )
                    encerradas += 1
                    break
    return encerradas


def _numero(valor) -> str:
    texto = str(valor or "").strip()
    return str(int(texto)) if texto.isdigit() else texto
