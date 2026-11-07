"""Sincronia diária com o PNCP: o que a empresa ganhou, sozinho.

Antes disso o Licita só sabia de uma licitação se alguém a salvasse na busca,
e não sabia que ela tinha sido ganha. Aqui, para cada CNPJ ativo em
Cadastros › Empresas, a API de Dados Abertos do Compras.gov.br (que espelha o
PNCP) devolve:

- **os itens homologados para o CNPJ** — viram `ItemParticipado` com
  `vencedor_e_a_empresa=True`. Se a compra não estava salva no Licita, ela é
  **criada aqui** (decisão da operação, 07/11/2026: nenhuma vitória pode
  ficar de fora);
- **os itens de ata de registro de preços** do CNPJ — viram
  `DocumentoFinanceiro` do tipo ata, com vigência e quantidade já empenhada.

Contrato fica de fora por enquanto: o módulo de contratos da API está
instável (Comunicado nº 18/26) e ainda não houve um contrato real da empresa
para conferir o formato. Até lá, contrato é lançado à mão.

Idempotente: rodar de novo atualiza, não duplica. Agendada todo dia às 8h
(`tasks.sincronizar_pncp`); também roda à mão com `manage.py sincronizar_pncp`.
"""

from __future__ import annotations

import datetime as dt
import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.empresas.models import Empresa
from apps.integracoes.clients.compras_gov import (
    ComprasGovClient,
    montar_link_compras_gov,
    montar_link_pncp,
)
from apps.integracoes.plataformas import plataforma_padrao

from .models import (
    DocumentoFinanceiro,
    EventoOportunidadeSalva,
    Fonte,
    ItemParticipado,
    OportunidadeSalva,
)

logger = logging.getLogger(__name__)

# Uma ata vale normalmente 1 ano (prorrogável): olhar 400 dias para trás
# cobre a ata inteira e os resultados que ainda podem virar empenho.
JANELA_DIAS = 400


def _chave_da_compra(id_contratacao: str) -> tuple[str, str, str] | None:
    """"16888315000157-1-000041/2026" → ("16888315000157", "2026", "41")."""

    try:
        cnpj, _, resto = id_contratacao.split("-", 2)
        sequencial, ano = resto.split("/")
        return cnpj, ano, str(int(sequencial))
    except (AttributeError, ValueError):
        return None


def _data(valor) -> dt.date | None:
    if not valor:
        return None
    try:
        return dt.date.fromisoformat(str(valor)[:10])
    except ValueError:
        return None


def _decimal(valor) -> Decimal | None:
    return Decimal(str(valor)) if valor is not None else None


def _numero_do_item(valor) -> str:
    """"00065" e 65 viram "65", como no edital."""

    texto = str(valor).strip()
    return str(int(texto)) if texto.isdigit() else texto


def _salva_da_compra(chave, id_compra: str, cliente, resumo: dict) -> OportunidadeSalva | None:
    cnpj, ano, sequencial = chave
    existente = (
        OportunidadeSalva.objects.ativas()
        .filter(cnpj_orgao=cnpj, ano_compra=ano, sequencial_compra__in={sequencial, sequencial.zfill(6)})
        .first()
    )
    if existente:
        if not existente.numero_processo:
            # O processo liga o empenho do Portal da Transparência à compra.
            processo = (cliente.detalhar_contratacao(id_compra) or {}).get("processo")
            if processo:
                existente.numero_processo = processo
                existente.save(update_fields=["numero_processo"])
        return existente

    contratacao = cliente.detalhar_contratacao(id_compra) or {}
    salva = OportunidadeSalva.objects.create(
        cnpj_orgao=cnpj,
        ano_compra=ano,
        sequencial_compra=sequencial,
        objeto=contratacao.get("objeto") or "",
        orgao_nome=contratacao.get("orgao_nome") or "",
        uasg=contratacao.get("uasg") or "",
        uf=contratacao.get("uf") or "",
        municipio=contratacao.get("municipio") or "",
        modalidade=contratacao.get("modalidade") or "",
        situacao=contratacao.get("situacao") or "",
        data_publicacao=_data(contratacao.get("data_publicacao")),
        data_encerramento_proposta=_data(contratacao.get("data_encerramento_proposta")),
        valor_total_estimado=_decimal(contratacao.get("valor_total_estimado")),
        numero_processo=contratacao.get("processo") or "",
        plataforma_id=plataforma_padrao().id,
        plataforma_nome=plataforma_padrao().nome,
        link_plataforma=(montar_link_compras_gov(contratacao) if contratacao else None) or "",
        link_pncp=(
            montar_link_pncp({"cnpj_orgao": cnpj, "ano_compra": ano, "sequencial_compra": sequencial}) or ""
        ),
    )
    salva.registrar(
        EventoOportunidadeSalva.Tipo.SALVA,
        autor=None,
        descricao="Trazida pela sincronia com o PNCP: a empresa venceu itens desta compra.",
    )
    resumo["salvas_criadas"] += 1
    return salva


def _gravar_resultado(registro: dict, cliente, resumo: dict) -> None:
    if registro.get("dataCancelamentoPncp"):
        return
    chave = _chave_da_compra(registro.get("idContratacaoPNCP") or registro.get("numeroControlePNCPCompra"))
    if not chave:
        logger.warning("Resultado do PNCP sem chave de compra: %s", registro.get("idCompraItem"))
        return

    salva = _salva_da_compra(chave, registro.get("idCompra"), cliente, resumo)
    item, criado = ItemParticipado.objects.get_or_create(
        oportunidade=salva,
        numero_item=_numero_do_item(registro["numeroItemPncp"]),
        defaults={"fonte": Fonte.PNCP},
    )
    item.vencedor_e_a_empresa = True
    item.valor_homologado = _decimal(registro.get("valorUnitarioHomologado"))
    item.quantidade = _decimal(registro.get("quantidadeHomologada")) or item.quantidade
    item.homologado_em = _data(registro.get("dataResultadoPncp"))
    item.save()
    resumo["itens"] += 1


def _gravar_item_de_ata(registro: dict, cliente, resumo: dict) -> None:
    if registro.get("itemExcluido"):
        return
    chave = _chave_da_compra(registro.get("numeroControlePncpCompra"))
    if not chave:
        return

    salva = _salva_da_compra(chave, registro.get("idCompra"), cliente, resumo)
    numero = _numero_do_item(registro["numeroItem"])
    item, _ = ItemParticipado.objects.get_or_create(
        oportunidade=salva,
        numero_item=numero,
        defaults={
            "fonte": Fonte.PNCP,
            "vencedor_e_a_empresa": True,
            "descricao": registro.get("descricaoItem") or "",
            "quantidade": _decimal(registro.get("quantidadeHomologadaItem")),
            "valor_homologado": _decimal(registro.get("valorUnitario")),
        },
    )
    if not item.descricao and registro.get("descricaoItem"):
        item.descricao = registro["descricaoItem"]
        item.save(update_fields=["descricao", "atualizado_em"])

    DocumentoFinanceiro.objects.update_or_create(
        fonte=Fonte.PNCP,
        tipo=DocumentoFinanceiro.Tipo.ATA,
        # Uma ata cobre vários itens do mesmo fornecedor: um documento por item.
        numero=f"{registro['numeroControlePncpAta']} item {numero}",
        defaults={
            "oportunidade": salva,
            "item": item,
            "data": _data(registro.get("dataAssinatura")),
            "vigente_ate": _data(registro.get("dataVigenciaFinal")),
            "valor": _decimal(registro.get("valorTotal")),
            "dados": {
                "numero_ata": registro.get("numeroAtaRegistroPreco"),
                "quantidade_homologada": registro.get("quantidadeHomologadaItem"),
                "quantidade_empenhada": registro.get("quantidadeEmpenhada"),
                "valor_unitario": registro.get("valorUnitario"),
            },
        },
    )
    resumo["atas"] += 1


def sincronizar_pncp(hoje: dt.date | None = None, cliente=None) -> dict[str, int]:
    """Lê resultados e atas de cada CNPJ ativo. Devolve o que fez."""

    hoje = hoje or timezone.localdate()
    inicio = (hoje - dt.timedelta(days=JANELA_DIAS)).isoformat()
    fim = hoje.isoformat()
    resumo = {"empresas": 0, "itens": 0, "atas": 0, "salvas_criadas": 0}

    cnpjs = sorted(set(Empresa.objects.filter(ativa=True).values_list("cnpj", flat=True)))
    proprio = cliente is None
    cliente = cliente or ComprasGovClient()
    try:
        for cnpj in cnpjs:
            resumo["empresas"] += 1
            resultados = cliente.resultados_do_fornecedor(cnpj, inicio, fim)
            atas = cliente.itens_de_ata_do_fornecedor(cnpj, inicio, fim)
            with transaction.atomic():
                for registro in resultados:
                    _gravar_resultado(registro, cliente, resumo)
                for registro in atas:
                    _gravar_item_de_ata(registro, cliente, resumo)
    finally:
        if proprio:
            cliente.close()
    return resumo
