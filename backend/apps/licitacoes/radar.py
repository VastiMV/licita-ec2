"""O Radar (GEN-68, 14/11/2026): busca automática de compras parecidas.

**Por quê:** o Carlinhos salva dezenas de oportunidades por mês, de itens que
se repetem. O Radar faz a busca por ele, todo dia às 8h e às 18h
(migration `0023_agenda_radar`), e deixa as compras achadas numa lista.

Regras da operação (cartão GEN-68 e respostas de 14/11/2026):

1. **Base** = os itens das oportunidades **salvas nos últimos 30 dias** + os
   itens que a Inside **ganhou** (qualquer data). O que foi só digitado na
   busca não conta (o Licita não guarda o histórico da busca).
2. **Onde:** todos os portais (busca textual do PNCP, sem filtro de
   plataforma) e o Brasil todo. A tela tem filtro de UF.
3. **O quê:** compras **recebendo proposta**, publicadas desde a rodada
   anterior (janela de `JANELA_DIAS`), que não estão salvas no Licita (nem
   tiradas da lista: quem tirou já decidiu).
4. **Quanto tempo:** a sugestão fica **7 dias ou até a abertura da
   disputa** (o prazo da proposta no PNCP), o que vier primeiro, e some
   sozinha (ajuste da operação, 14/11/2026). No dia da abertura ela ainda
   aparece: a proposta pode ser enviada até a hora da sessão, e o Licita só
   guarda o dia.
5. **Aviso:** só o número no botão Radar do topo.

**"Parecido" (decisão técnica):** a descrição do item vira o termo da busca
pelo **tipo do catálogo** (PDM: "Ração suplementar para aves" → o nome do
PDM, como em `mercado.achar_pdm`); sem PDM, as primeiras palavras da
descrição. Ganho vem antes de salvo, e a rodada tem um teto de termos
(`MAX_TERMOS`) para não estourar o PNCP (ele limita por IP).
"""

from __future__ import annotations

import datetime as dt
import logging
import re
import time
from decimal import Decimal

from django.db.models import Exists, OuterRef
from django.utils import timezone

from apps.integracoes.clients.pncp import TAM_PAGINA_MAX, PncpClient, PncpClientError

from . import radar_ia
from .mercado import achar_pdm, normalizar
from .models import ItemParticipado, OportunidadeSalva, SugestaoRadar, montar_texto_busca

logger = logging.getLogger(__name__)

DIAS_DA_BASE = 30
DIAS_NO_RADAR = 7
JANELA_DIAS = 2  # publicadas de anteontem para cá: as rodadas se sobrepõem
MAX_TERMOS = 30
PALAVRAS_SEM_PDM = 4


ESPERA_429 = 5  # segundos; dobra a cada tentativa (5, 10, 20)
TENTATIVAS_429 = 4
PAUSA_ENTRE_TERMOS = 2  # segundos
# Pedidos ao mesmo tempo. A busca da tela usa 20 (tem gente esperando); com
# 20, a rodada real de 14/11 levou 240 respostas 429 em 4 termos.
WORKERS = 3


class PncpPaciente(PncpClient):
    """O cliente do PNCP para o Radar: espera e tenta de novo quando o PNCP
    responde **429** ("devagar"). O cliente normal não repete o 429 (a busca
    da tela tem gente esperando). O Radar roda sozinho, então pode esperar.

    Achado de 14/11/2026, numa rodada real com 4 termos: vários 429 no
    detalhe da compra, e compra sem detalhe é descartada calada (sem link não
    há oportunidade). Com 30 termos, perderia muito mais."""

    def _get_com_repeticao(self, caminho, params):
        for tentativa in range(1, TENTATIVAS_429 + 1):
            try:
                return super()._get_com_repeticao(caminho, params)
            except PncpClientError as exc:
                if "respondeu 429" not in str(exc) or tentativa == TENTATIVAS_429:
                    raise
                time.sleep(ESPERA_429 * 2 ** (tentativa - 1))
        raise AssertionError("inalcançável")  # pragma: no cover


def _nome_do_item(descricao: str) -> str:
    """O nome do item numa descrição do catálogo, que segue o padrão
    `<nome> <atributo>: <valor>, <atributo>: <valor>` — o que vem antes do
    primeiro ":", sem a última palavra (o nome do atributo).

    Teste no servidor (15/11/2026): "Tonômetro modelo: goldman, tipo base:
    móvel" virava o termo "tonometro modelo goldman tipo" (as 4 primeiras
    palavras), e "tipo", "serviço", "aplicação" puxavam compras sem relação.
    Agora vira "Tonômetro". Sem ":", as primeiras palavras."""

    if ":" in descricao:
        antes = descricao.split(":", 1)[0].strip()
        if " " in antes:
            nome = antes.rsplit(" ", 1)[0].strip(" -,")
            if nome:
                return nome
    return " ".join(descricao.split()[:PALAVRAS_SEM_PDM])


AGRUPAMENTO = re.compile(r"^\s*(grupo|lote|item)\s*\d+\s*[-–:.)]?\s*", re.IGNORECASE)


def _sem_agrupamento(descricao: str) -> str:
    """"Grupo 3", "Lote 2 - Luva…" (17/11/2026, operação): o nome do
    agrupamento não é produto — "Grupo 3" sozinho fica fora da base, e
    "Lote 2 - Luva" vira "Luva". Buscar "grupo 3" trazia muito lixo."""

    resto = AGRUPAMENTO.sub("", descricao or "").strip()
    return resto if len(normalizar(resto)) >= 3 else ""


def _termo(descricao: str) -> str:
    """O que se procura no PNCP para uma descrição de item: o tipo do
    catálogo (PDM) ou, sem ele, o nome do item (`_nome_do_item`)."""

    pdm = achar_pdm(descricao)
    if pdm:
        return pdm.nome_pdm
    # Sem acento, como nas rodadas reais que funcionaram (14 e 15/11/2026).
    return normalizar(_nome_do_item(descricao)).lower()


def termos_da_base(hoje: dt.date | None = None) -> list[tuple[str, str, bool]]:
    """`(termo, descrição de origem, por_ganho)`, sem repetir termo. Ganho
    primeiro; no máximo `MAX_TERMOS`."""

    hoje = hoje or timezone.localdate()
    inicio = timezone.make_aware(dt.datetime.combine(hoje - dt.timedelta(days=DIAS_DA_BASE), dt.time.min))
    descricoes: list[tuple[str, bool]] = [
        (d, True)
        for d in ItemParticipado.objects.filter(vencedor_e_a_empresa=True)
        .exclude(descricao="")
        .order_by("-atualizado_em")
        .values_list("descricao", flat=True)
    ]
    for itens in (
        OportunidadeSalva.objects.ativas().filter(criada_em__gte=inicio).order_by("-criada_em").values_list("itens", flat=True)
    ):
        for item in itens or []:
            if descricao := (item.get("descricao_resumida") or "").strip():
                descricoes.append((descricao, False))

    vistos: set[str] = set()
    termos: list[tuple[str, str, bool]] = []
    for descricao, por_ganho in descricoes:
        descricao = _sem_agrupamento(descricao)
        if not descricao:
            continue
        termo = _termo(descricao)
        chave = normalizar(termo)
        if not chave or chave in vistos:
            continue
        vistos.add(chave)
        termos.append((termo, descricao, por_ganho))
        if len(termos) >= MAX_TERMOS:
            break
    return termos


def _data(valor) -> dt.date | None:
    if not isinstance(valor, str):
        return None
    try:
        return dt.date.fromisoformat(valor[:10])
    except ValueError:
        return None


def _valor_total(itens: list[dict]) -> Decimal | None:
    valores = [i.get("valor_total") for i in itens]
    if not valores or any(v is None for v in valores):
        return None
    return Decimal(str(sum(valores)))


def _chave(item: dict) -> tuple[str, str, str]:
    return (
        str(item.get("contratacao_cnpj_orgao") or ""),
        str(item.get("contratacao_ano_compra") or ""),
        str(item.get("contratacao_sequencial_compra") or ""),
    )


def _ja_conhecidas() -> set[tuple[str, str, str]]:
    """Salvas (inclusive as tiradas da lista) e as que já estão no Radar."""

    conhecidas = set(
        OportunidadeSalva.objects.values_list("cnpj_orgao", "ano_compra", "sequencial_compra")
    )
    conhecidas |= set(SugestaoRadar.objects.values_list("cnpj_orgao", "ano_compra", "sequencial_compra"))
    return conhecidas


PALAVRAS_VAZIAS = {"DE", "DA", "DO", "DAS", "DOS", "PARA", "E", "COM", "EM", "A", "O", "AS", "OS"}
MAX_PAGINAS_DE_ITENS = 10  # 500 itens


def _palavras(termo: str) -> list[str]:
    return [p for p in normalizar(termo).split() if p not in PALAVRAS_VAZIAS]


def item_casa(termo: str, item: dict) -> bool:
    """O item tem **todas** as palavras do termo (sem "de", "para"…; plural
    conta: "luva" casa "LUVAS"). Regra da operação, 17/11/2026: só entra no
    Radar a compra com pelo menos 1 item assim. No teste real, sem essa
    regra, 46 de 69 sugestões não tinham relação ("lâmpada fenda" trazia
    abraçadeira e alicate)."""

    palavras = _palavras(termo)
    if not palavras:
        return False
    texto = normalizar(f"{item.get('descricao_resumida') or ''} {item.get('descricao_detalhada') or ''}")
    tokens = texto.split()
    return all(any(t.startswith(p) for t in tokens) for p in palavras)


def todos_os_itens(cliente, cnpj: str, ano: str, sequencial: str) -> list[dict]:
    """Todos os itens da compra, página por página (o PNCP devolve 50 por
    vez): a seringa pode ser o item 120. Erro do PNCP sobe."""

    itens: list[dict] = []
    for pagina in range(1, MAX_PAGINAS_DE_ITENS + 1):
        lote = cliente.listar_itens(cnpj=cnpj, ano=ano, sequencial=sequencial, pagina=pagina)
        itens.extend(lote)
        if len(lote) < TAM_PAGINA_MAX:
            break
    return itens


def _linhas(base: dict, itens: list[dict], termo: str) -> tuple[list[dict], bool]:
    """Os itens no formato da busca, **os que casam primeiro** (o card os
    mostra no topo). Devolve também se algum casou."""

    linhas = []
    for item in itens:
        linha = dict(base)
        linha.update({campo: item.get(campo) for campo in CAMPOS_DO_ITEM})
        linha["situacao_item"] = item.get("situacao")
        linhas.append(linha)
    casam = [l for l in linhas if item_casa(termo, l)]
    resto = [l for l in linhas if not item_casa(termo, l)]
    return casam + resto, bool(casam)


def rodar(hoje: dt.date | None = None, pncp: PncpClient | None = None) -> dict[str, int]:
    """Uma rodada do Radar: limpa as vencidas e procura as novas."""

    from .services import _buscar_no_pncp

    hoje = hoje or timezone.localdate()
    resumo = {
        "termos": 0,
        "novas": 0,
        "sem_item_que_casa": 0,
        "removidas": limpar(hoje),
        "falhas": 0,
        "itens_completados": 0,
        "aprovadas_ia": 0,
        "reprovadas_ia": 0,
        "ia_falhou": 0,
    }
    termos = termos_da_base(hoje)
    resumo["termos"] = len(termos)

    proprio = pncp is None
    cliente = pncp or PncpPaciente()
    resumo["itens_completados"] = completar_itens(cliente, hoje)
    if not termos:
        if proprio:
            cliente.close()
        return resumo
    conhecidas = _ja_conhecidas()
    itens_da_compra: dict[tuple[str, str, str], list[dict] | None] = {}
    try:
        for n, (termo, origem, por_ganho) in enumerate(termos):
            if n and proprio:
                time.sleep(PAUSA_ENTRE_TERMOS)  # gentileza com o limite por IP
            try:
                achados = _buscar_no_pncp(
                    termo,
                    data_inicial=(hoje - dt.timedelta(days=JANELA_DIAS)).isoformat(),
                    data_final=hoje.isoformat(),
                    codigo_modalidade="",
                    uf=None,
                    codigo_unidade=None,
                    plataforma=None,
                    pncp_client=cliente,
                    workers=WORKERS,
                    com_itens=False,
                ) or []
            except PncpClientError:
                resumo["falhas"] += 1
                logger.warning('Radar: o PNCP falhou na busca de "%s"', termo)
                continue

            por_compra: dict[tuple[str, str, str], list[dict]] = {}
            for item in achados:
                chave = _chave(item)
                if all(chave) and chave not in conhecidas:
                    por_compra.setdefault(chave, []).append(item)

            for chave, achado in por_compra.items():
                primeiro = achado[0]
                prazo = _data(primeiro.get("contratacao_data_encerramento_proposta"))
                if prazo and prazo < hoje:
                    continue
                if chave not in itens_da_compra:
                    try:
                        itens_da_compra[chave] = todos_os_itens(cliente, *chave)
                    except PncpClientError:
                        itens_da_compra[chave] = None  # sem itens agora: fica pendente
                brutos = itens_da_compra[chave]
                if brutos is None or not brutos:
                    # Não dá para saber se casa: entra **pendente** (a tela
                    # não mostra) e a próxima rodada decide (`completar_itens`).
                    itens = [primeiro]
                else:
                    itens, casou = _linhas(primeiro, brutos, termo)
                    if not casou:
                        resumo["sem_item_que_casa"] += 1
                        continue  # outro termo ainda pode casar com esta compra
                objeto = primeiro.get("contratacao_objeto") or ""
                nota = None
                if radar_ia.ligada() and brutos:
                    avaliacao = radar_ia.avaliar(termo, objeto, [i for i in itens if item_casa(termo, i)])
                    if avaliacao is None:
                        resumo["ia_falhou"] += 1
                        continue  # não guarda: a próxima rodada tenta de novo
                    nota = avaliacao.nota
                    resumo["aprovadas_ia" if nota >= radar_ia.NOTA_MINIMA else "reprovadas_ia"] += 1
                SugestaoRadar.objects.create(
                    cnpj_orgao=chave[0],
                    ano_compra=chave[1],
                    sequencial_compra=chave[2],
                    objeto=objeto,
                    orgao_nome=(primeiro.get("contratacao_orgao_nome") or "")[:255],
                    uasg=primeiro.get("contratacao_uasg") or "",
                    uf=(primeiro.get("contratacao_uf") or "")[:2],
                    municipio=(primeiro.get("contratacao_municipio") or "")[:255],
                    modalidade=(primeiro.get("contratacao_modalidade") or "")[:120],
                    data_publicacao=_data(primeiro.get("contratacao_data_publicacao")),
                    data_encerramento_proposta=prazo,
                    valor_total_estimado=_valor_total(itens),
                    plataforma_id=primeiro.get("plataforma_id") or "",
                    link_plataforma=primeiro.get("link_plataforma") or "",
                    link_pncp=primeiro.get("link_pncp") or "",
                    itens=itens,
                    texto_busca=montar_texto_busca(objeto, itens),
                    parecido_com=origem[:255],
                    por_ganho=por_ganho,
                    expira_em=_expira_em(hoje, prazo),
                    nota_ia=nota,
                )
                conhecidas.add(chave)
                resumo["novas"] += 1
    finally:
        if proprio:
            cliente.close()
    return resumo


def _expira_em(hoje: dt.date, prazo: dt.date | None) -> dt.date:
    """O dia em que some: 7 dias depois de achada, ou o dia seguinte à
    abertura da disputa — o que vier primeiro."""

    sete_dias = hoje + dt.timedelta(days=DIAS_NO_RADAR)
    return min(sete_dias, prazo + dt.timedelta(days=1)) if prazo else sete_dias


CAMPOS_DO_ITEM = (
    "numero_item",
    "descricao_resumida",
    "descricao_detalhada",
    "material_ou_servico",
    "quantidade",
    "unidade_medida",
    "valor_unitario_estimado",
    "valor_total",
    "criterio_julgamento",
    "tipo_beneficio",
)


def completar_itens(cliente, hoje: dt.date) -> int:
    """Sugestões pendentes (entraram sem itens porque o PNCP não devolveu):
    tenta de novo a cada rodada. Com os itens, vale a regra de entrada — sem
    item que casa, a sugestão é apagada. Achado do teste de 15/11/2026: o
    serviço de itens do PNCP ficou fora do ar e 67 sugestões entraram sem
    itens."""

    from .completar import sem_itens

    completadas = 0
    for sugestao in SugestaoRadar.objects.filter(expira_em__gt=hoje, removida_em__isnull=True):
        if not sem_itens(sugestao.itens):
            continue
        try:
            brutos = todos_os_itens(cliente, sugestao.cnpj_orgao, sugestao.ano_compra, sugestao.sequencial_compra)
        except PncpClientError:
            continue
        if not brutos:
            continue
        base = sugestao.itens[0] if sugestao.itens else {}
        termo = _termo(sugestao.parecido_com)
        itens, casou = _linhas(base, brutos, termo)
        if not casou:
            sugestao.delete()
            continue
        if radar_ia.ligada():
            avaliacao = radar_ia.avaliar(termo, sugestao.objeto, [i for i in itens if item_casa(termo, i)])
            if avaliacao is None:
                continue  # fica pendente; a próxima rodada tenta de novo
            sugestao.nota_ia = avaliacao.nota
        sugestao.itens = itens
        sugestao.valor_total_estimado = _valor_total(itens)
        sugestao.texto_busca = montar_texto_busca(sugestao.objeto, itens)
        sugestao.save(update_fields=["itens", "valor_total_estimado", "texto_busca", "nota_ia"])
        completadas += 1
    return completadas


def limpar(hoje: dt.date | None = None) -> int:
    """Apaga as que fizeram 7 dias no Radar ou cuja disputa já abriu."""

    hoje = hoje or timezone.localdate()
    # As removidas por ele ficam: são o exemplo do que ele não quer (GEN-93),
    # e não voltam ao Radar (`_ja_conhecidas`).
    apagadas, _ = SugestaoRadar.objects.filter(expira_em__lte=hoje, removida_em__isnull=True).delete()
    return apagadas


def visiveis(hoje: dt.date | None = None):
    """As que a tela mostra: dentro dos 7 dias, prazo aberto, e que ninguém
    salvou depois (salvar pelo card tira do Radar)."""

    hoje = hoje or timezone.localdate()
    salvas = OportunidadeSalva.objects.filter(
        cnpj_orgao=OuterRef("cnpj_orgao"),
        ano_compra=OuterRef("ano_compra"),
        sequencial_compra=OuterRef("sequencial_compra"),
    )
    return (
        SugestaoRadar.objects.filter(expira_em__gt=hoje, removida_em__isnull=True)
        .exclude(data_encerramento_proposta__lt=hoje)
        # Pendentes (sem itens ainda): não dá para saber se casam.
        .exclude(itens__0__descricao_resumida=None)
        # Reprovadas pela IA ficam guardadas, mas não aparecem (GEN-93).
        .exclude(nota_ia__lt=radar_ia.NOTA_MINIMA)
        .exclude(Exists(salvas))
    )
