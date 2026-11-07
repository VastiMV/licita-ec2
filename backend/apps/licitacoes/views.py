"""Endpoints do app de licitações.

**Busca** (`OportunidadesView`, `CompraDetalheView`): consulta ao vivo, não
persiste (ver docs/DOMINIO.md). Parâmetros batem 1:1 com
`OportunidadeBuscaParams` no frontend
(`frontend/src/app/contracts/licitacoes/oportunidade.contracts.ts`).

**Oportunidades salvas** (`OportunidadesSalvasView` e as demais no fim do
arquivo): a lista que a equipe monta a partir da busca — persiste, com
histórico. Ver `models.py` para as duas decisões que moldam essas views (a
lista é compartilhada por todos os usuários; remover é lógico, para o log
sobreviver).
"""

from __future__ import annotations

import datetime as dt

from django.shortcuts import get_object_or_404
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.capag.lookup import nota_para
from apps.catalogo.search import buscar_pdms
from apps.integracoes.clients.compras_gov import ComprasGovClientError
from apps.integracoes.clients.pncp import PncpClient, PncpClientError
from apps.integracoes.plataformas import identificar_plataforma, plataforma_padrao

from .ciclo import montar_quadro
from .encerradas import MOTIVOS, MOTIVOS_DESCARTE, descartadas, encerradas, montar_processo
from .models import OportunidadeSalva, registrar_prazos_vencidos
from .salvas import garantir_salva
from .serializers import (
    CompraDetalheSerializer,
    DescartadaSerializer,
    EmCotacaoSerializer,
    EncerradaSerializer,
    EventoOportunidadeSalvaSerializer,
    OportunidadeSalvaSerializer,
    OportunidadeSerializer,
)
from .services import (
    BuscaSemCorrespondenciaNoCatalogo,
    buscar_oportunidades,
    detalhar_compra_cacheada,
)

# Mesma janela padrão do protótipo (`app/routers/licitacoes.py`) para o modo
# interativo — diferente do lookback de 2 dias usado pelo scanner de
# `Filtro`/`Alerta` (que roda com muito mais frequência).
JANELA_PADRAO_DIAS = 30


class OportunidadesView(APIView):
    def get(self, request: Request) -> Response:
        params = request.query_params

        hoje = dt.date.today()
        data_final = params.get("data_final") or hoje.isoformat()
        data_inicial = (
            params.get("data_inicial") or (hoje - dt.timedelta(days=JANELA_PADRAO_DIAS)).isoformat()
        )
        palavra_chave = (params.get("palavra_chave") or "").strip()
        uf = params.get("uf") or None
        codigo_unidade = params.get("codigo_unidade") or None
        modalidade = params.get("modalidade") or ""

        # Resolvido ANTES de chamar a orquestração — camadas 1+2 da busca
        # textual (ver apps/catalogo/search.py e docs/DOMINIO.md). Só entra
        # em jogo se o PNCP (camada preferida, dentro de services.py) falhar
        # ou não achar nada.
        codigos_pdm = [p.codigo_pdm for p in buscar_pdms(palavra_chave)] if palavra_chave else None

        try:
            # O client de navegação/fallback vem do registro de plataformas
            # (`apps/integracoes/plataformas.py`) — é lá que uma plataforma
            # nova entra, não aqui.
            with plataforma_padrao().criar_client() as client:
                resultados = buscar_oportunidades(
                    client,
                    data_inicial=data_inicial,
                    data_final=data_final,
                    codigo_modalidade=modalidade,
                    palavra_chave=palavra_chave,
                    codigos_pdm=codigos_pdm,
                    uf=uf,
                    codigo_unidade=codigo_unidade,
                )
        except BuscaSemCorrespondenciaNoCatalogo:
            # Não é erro — nem PNCP nem catálogo acharam nada para o termo.
            # Frontend trata lista vazia como "sem resultados", não como falha.
            resultados = []
        except ComprasGovClientError as exc:
            return Response({"detail": str(exc)}, status=502)

        _resolver_capag(resultados)
        serializer = OportunidadeSerializer(resultados, many=True)
        return Response(serializer.data)


def _resolver_capag(resultados: list[dict]) -> None:
    """Preenche `capag` nas oportunidades cujos insumos (esfera + IBGE) a
    busca já trouxe — o caminho da busca textual os pega do mesmo detalhe
    que filtra a plataforma, de graça. Importa porque o `/api/consulta/` do
    PNCP tem rate limit por IP (ver docs/DOMINIO.md, 28/08/2026): a chamada
    de detalhe do card, disparada logo após a busca, leva 429 — se o selo
    dependesse só dela, sumiria. Nos caminhos sem insumos (navegação/PDM),
    `capag` fica nulo e o detalhe do card continua sendo quem resolve.

    Resolve aqui, e não em services, porque a nota vem do banco
    (`apps.capag`) e a orquestração de busca é deliberadamente sem banco.
    """

    memo: dict[tuple, dict | None] = {}
    for op in resultados:
        chave = (op.get("capag_esfera_id"), op.get("capag_codigo_ibge"), op.get("contratacao_uf"))
        if chave not in memo:
            memo[chave] = nota_para(esfera_id=chave[0], codigo_ibge=chave[1], uf=chave[2])
        op["capag"] = memo[chave]


class CompraDetalheView(APIView):
    """`GET /api/licitacoes/compras/<cnpj>/<ano>/<sequencial>/detalhe/` —
    documentos do edital (com link de download direto), selo CAPAG e a
    plataforma de origem de uma compra específica.

    Uma chamada por card, disparada pelo frontend quando o resultado da busca
    chega — nunca N chamadas dentro da própria busca (não queremos voltar à
    lentidão já corrigida, ver docs/DOMINIO.md).
    """

    def get(self, request: Request, cnpj: str, ano: int, sequencial: int) -> Response:
        capag = None
        documentos: list[dict] = []
        plataforma = None

        with PncpClient() as client:
            try:
                # Cacheado: a busca que gerou este card provavelmente acabou
                # de detalhar esta mesma compra — e o /api/consulta/ tem rate
                # limit por IP que a rajada dela consome (ver services).
                detalhe = detalhar_compra_cacheada(
                    client, cnpj=cnpj, ano=ano, sequencial=sequencial
                )
            except PncpClientError:
                detalhe = None
            if detalhe:
                capag = nota_para(
                    esfera_id=detalhe.get("esfera_id"),
                    codigo_ibge=detalhe.get("codigo_ibge"),
                    uf=detalhe.get("uf"),
                )
                # O link de origem é a resposta definitiva de "em qual
                # plataforma essa compra acontece" — corrige o palpite da
                # busca (ver `services._montar_oportunidade`). Plataforma não
                # registrada ainda assim tem link e nome (os que o PNCP deu);
                # só fica sem `id` (logo, sem ícone próprio no frontend).
                link_plataforma = detalhe.get("link_plataforma")
                if link_plataforma:
                    conhecida = identificar_plataforma(link_plataforma)
                    plataforma = {
                        "id": conhecida.id if conhecida else None,
                        "nome": conhecida.nome if conhecida else detalhe.get("plataforma_nome"),
                        "link": link_plataforma,
                    }

            try:
                documentos = client.listar_arquivos(cnpj=cnpj, ano=ano, sequencial=sequencial)
            except PncpClientError:
                documentos = []

        serializer = CompraDetalheSerializer(
            {"documentos": documentos, "capag": capag, "plataforma": plataforma}
        )
        return Response(serializer.data)


class OportunidadesSalvasPaginacao(PageNumberPagination):
    """Paginação só desta lista (o resto da API não é paginado). Página
    pequena porque a tabela do frontend é o consumidor — quem quiser mais
    pede `page_size`."""

    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


# Colunas ordenáveis da tabela do frontend -> campo real. Whitelist, não
# `OrderingFilter` aberto: o nome da coluna é contrato de tela, e ordenar por
# um campo interno (`texto_busca`, `itens`) não faz sentido nenhum. O objeto
# do edital não está aqui porque saiu da tabela — continua sendo o texto que
# a busca varre (`texto_busca`), só não é coluna.
ORDENACOES = {
    "uasg": "uasg",
    "modalidade": "modalidade",
    "cidade": "municipio",
    "data_publicacao": "data_publicacao",
    "prazo": "data_encerramento_proposta",
    "valor": "valor_total_estimado",
    "criada_em": "criada_em",
}
ORDENACAO_PADRAO = "-criada_em"


def _ordenacao(pedida: str | None) -> str:
    """Traduz `ordering=-prazo` (nome de coluna) para o campo do model.
    Coluna desconhecida cai no padrão em vez de estourar 400 — ordenação é
    preferência de exibição, não parâmetro crítico."""

    pedida = (pedida or "").strip()
    descendente = pedida.startswith("-")
    campo = ORDENACOES.get(pedida.lstrip("-"))
    if not campo:
        return ORDENACAO_PADRAO
    return f"-{campo}" if descendente else campo


class OportunidadesSalvasView(APIView):
    """`GET/POST /api/licitacoes/salvas/`.

    A lista é da equipe inteira, não do usuário logado (decisão de produto —
    ver docstring de `models.py`): não há filtro por dono nem no GET nem no
    DELETE.
    """

    def get(self, request: Request) -> Response:
        # O log ganha a linha "prazo encerrado" no momento em que alguém
        # abre a lista — ver `registrar_prazos_vencidos` para o porquê de
        # não haver task periódica.
        registrar_prazos_vencidos()

        # Só a etapa Oportunidade: com cotação, a licitação está no Cotador;
        # com o prazo vencido, está em Encerradas.
        salvas = (
            OportunidadeSalva.objects.ativas()
            .sem_cotacao()
            .no_prazo()
            .buscar(request.query_params.get("busca", ""))
            .order_by(_ordenacao(request.query_params.get("ordering")))
        )

        paginacao = OportunidadesSalvasPaginacao()
        pagina = paginacao.paginate_queryset(salvas, request, view=self)
        return paginacao.get_paginated_response(
            OportunidadeSalvaSerializer(pagina, many=True).data
        )

    def post(self, request: Request) -> Response:
        # Idempotente (salvar de novo devolve o registro existente, sem
        # evento novo) — a regra mora em `salvas.garantir_salva`, porque o
        # Cotador também salva a oportunidade por esse mesmo caminho.
        salva, criada = garantir_salva(request.data, request=request)
        return Response(
            OportunidadeSalvaSerializer(salva).data, status=201 if criada else 200
        )


class OportunidadeSalvaView(APIView):
    """`DELETE /api/licitacoes/salvas/<id>/` — tira da lista. Remoção lógica:
    o histórico continua existindo (ver `models.OportunidadeSalva.remover`)."""

    def delete(self, request: Request, pk: int) -> Response:
        salva = get_object_or_404(OportunidadeSalva.objects.ativas(), pk=pk)
        salva.remover(por=request.user)
        return Response(status=204)


class OportunidadesSalvasChavesView(APIView):
    """`GET /api/licitacoes/salvas/chaves/` — só as chaves (`cnpj-ano-seq`)
    das que estão na lista.

    Existe para a tela de busca saber quais cards já estão salvos sem baixar
    a lista inteira (e sem lidar com a paginação dela) — salvar não é mais um
    toggle: o que já está salvo só sai pelo módulo de salvas.
    """

    def get(self, request: Request) -> Response:
        chaves = [
            f"{cnpj}-{ano}-{seq}"
            for cnpj, ano, seq in OportunidadeSalva.objects.ativas().values_list(
                "cnpj_orgao", "ano_compra", "sequencial_compra"
            )
        ]
        return Response({"chaves": chaves})


class OportunidadeSalvaEventosView(APIView):
    """`GET /api/licitacoes/salvas/<id>/eventos/` — o histórico de uma
    oportunidade salva: o registro principal (o que foi salvo, por quem,
    quando) e a lista do que aconteceu depois, em ordem.

    O módulo de tela que lê isso ainda não existe (ver docs/DOMINIO.md,
    "Histórico da oportunidade salva"); o endpoint existe porque o log já é
    escrito — inclusive para oportunidades removidas, que continuam
    consultáveis por aqui.
    """

    def get(self, request: Request, pk: int) -> Response:
        salva = get_object_or_404(OportunidadeSalva, pk=pk)
        eventos = salva.eventos.all()
        return Response(
            {
                "id": salva.id,
                "chave": salva.chave,
                "resumo": salva.resumo,
                "salva_por": salva.salva_por_nome or None,
                "criada_em": salva.criada_em,
                "removida_em": salva.removida_em,
                "eventos": EventoOportunidadeSalvaSerializer(eventos, many=True).data,
            }
        )


# O Cotador ordena pelas mesmas colunas da Salvas, mais as da cotação.
ORDENACOES_COTADOR = {
    **ORDENACOES,
    "atualizada_em": "cotacao__atualizada_em",
    "valor_cotado": "cotacao__valor_cotado",
}


class EmCotacaoView(APIView):
    """`GET /api/licitacoes/cotacoes/` — a lista do Cotador: as salvas na
    etapa Cotação (com cotação, sem proposta, prazo aberto). Gerou proposta,
    sai daqui;
    prazo vencido, vai para Encerradas."""

    def get(self, request: Request) -> Response:
        registrar_prazos_vencidos()
        params = request.query_params

        pedida = (params.get("ordering") or "").strip()
        campo = ORDENACOES_COTADOR.get(pedida.lstrip("-"))
        ordem = (f"-{campo}" if pedida.startswith("-") else campo) if campo else "data_encerramento_proposta"

        lista = (
            OportunidadeSalva.objects.ativas()
            .filter(cotacao__isnull=False)
            .sem_proposta()
            .no_prazo()
            .buscar(params.get("busca", ""))
            .select_related("cotacao")
            .prefetch_related("cotacao__itens__ofertas")
            .order_by(ordem, "id")
        )

        paginacao = OportunidadesSalvasPaginacao()
        pagina = paginacao.paginate_queryset(lista, request, view=self)
        return paginacao.get_paginated_response(EmCotacaoSerializer(pagina, many=True).data)


class CicloView(APIView):
    """`GET /api/licitacoes/ciclo/` — o quadro do Ciclo de Licitação: uma
    coluna por etapa, com a etapa calculada (ver `ciclo.py`)."""

    def get(self, request: Request) -> Response:
        return Response(montar_quadro())


ORDENACOES_ENCERRADAS = {
    "uasg": "uasg",
    "cidade": "municipio",
    "encerrada_em": "encerrada_em",
    "motivo": "motivo",
    "valor": "valor_total_estimado",
}


def _data(valor: str | None) -> dt.date | None:
    try:
        return dt.date.fromisoformat(valor) if valor else None
    except ValueError:
        return None


class EncerradasView(APIView):
    """`GET /api/licitacoes/encerradas/` — as licitações que saíram do ciclo
    (ver `encerradas.py`), com os filtros da tela: período de encerramento
    (`data_inicial`/`data_final`), `motivo`, `uf` e `busca` textual."""

    def get(self, request: Request) -> Response:
        registrar_prazos_vencidos()
        params = request.query_params

        lista = encerradas().select_related("cotacao").buscar(params.get("busca", ""))
        if inicio := _data(params.get("data_inicial")):
            lista = lista.filter(encerrada_em__gte=inicio)
        if fim := _data(params.get("data_final")):
            lista = lista.filter(encerrada_em__lte=fim)
        if (motivo := params.get("motivo")) in MOTIVOS:
            lista = lista.filter(motivo=motivo)
        if uf := (params.get("uf") or "").strip().upper():
            lista = lista.filter(uf=uf)

        pedida = (params.get("ordering") or "").strip()
        campo = ORDENACOES_ENCERRADAS.get(pedida.lstrip("-"))
        ordem = (f"-{campo}" if pedida.startswith("-") else campo) if campo else "-encerrada_em"
        lista = lista.order_by(ordem, "-id")

        paginacao = OportunidadesSalvasPaginacao()
        pagina = paginacao.paginate_queryset(lista, request, view=self)
        return paginacao.get_paginated_response(EncerradaSerializer(pagina, many=True).data)


ORDENACOES_DESCARTADAS = {
    "uasg": "uasg",
    "cidade": "municipio",
    "descartada_em": "descartada_em",
    "motivo": "motivo",
    "valor": "valor_total_estimado",
}


class DescartadasView(APIView):
    """`GET /api/licitacoes/descartadas/` — tiradas da lista antes do prazo
    e vencidas sem cotação (ver `encerradas.descartadas`), com os filtros da
    tela: período do descarte (`data_inicial`/`data_final`), `motivo`, `uf`
    e `busca` textual."""

    def get(self, request: Request) -> Response:
        registrar_prazos_vencidos()
        params = request.query_params

        lista = descartadas().select_related("cotacao").buscar(params.get("busca", ""))
        if inicio := _data(params.get("data_inicial")):
            lista = lista.filter(descartada_em__gte=inicio)
        if fim := _data(params.get("data_final")):
            lista = lista.filter(descartada_em__lte=fim)
        if (motivo := params.get("motivo")) in MOTIVOS_DESCARTE:
            lista = lista.filter(motivo=motivo)
        if uf := (params.get("uf") or "").strip().upper():
            lista = lista.filter(uf=uf)

        pedida = (params.get("ordering") or "").strip()
        campo = ORDENACOES_DESCARTADAS.get(pedida.lstrip("-"))
        ordem = (f"-{campo}" if pedida.startswith("-") else campo) if campo else "-descartada_em"
        lista = lista.order_by(ordem, "-id")

        paginacao = OportunidadesSalvasPaginacao()
        pagina = paginacao.paginate_queryset(lista, request, view=self)
        return paginacao.get_paginated_response(DescartadaSerializer(pagina, many=True).data)


class ProcessoView(APIView):
    """`GET /api/licitacoes/salvas/<id>/processo/` — a história da salva no
    formato do modal do processo (ver `encerradas.montar_processo`). Vale
    também para removidas: rastreabilidade é o motivo de a remoção ser
    lógica."""

    def get(self, request: Request, pk: int) -> Response:
        return Response(montar_processo(get_object_or_404(OportunidadeSalva, pk=pk)))
