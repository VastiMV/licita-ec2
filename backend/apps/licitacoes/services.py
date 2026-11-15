"""Orquestra a busca "por item" de oportunidades (ver docs/DOMINIO.md, "Busca
de oportunidades" e "Busca textual — camadas").

A busca por palavra tem dois caminhos, tentados nesta ordem:

**1. Busca textual do PNCP** (`apps/integracoes/clients/pncp.py`) — o endpoint
por trás da caixa de busca de pncp.gov.br/app/editais. Casa a palavra com o
*objeto do edital*. É o caminho preferido: pega material e serviço, e não
depende do catálogo local.

**2. Catálogo local de PDM** (`apps/catalogo/search.py`) — mantido como
reserva porque o endpoint do PNCP não é documentado e pode mudar sem aviso.
A view resolve a palavra em códigos de PDM (camadas 1+2 da busca por
similaridade) *antes* de chamar `buscar_oportunidades` — este módulo só
consome `codigos_pdm` já resolvidos.

A reserva entra sozinha quando o PNCP falha ou devolve vazio. Ela só cobre
material, então acha menos coisa que a busca textual.

Sem palavra-chave, o modo é de navegação: lista as contratações do período
(por modalidade/UF/UASG) no compras.gov.br e desdobra cada uma nos itens que
o PNCP publica (ver `_itens_da_compra` — o mirror de itens do compras.gov.br
está semanas atrás do de contratações). Não depende do catálogo.
É por aí que passa a **busca por UASG** da tela (a tela deixa escolher entre
buscar por palavra-chave OU por UASG, nunca os dois): a unidade é filtro
nativo do compras.gov.br (`unidadeOrgaoCodigoUnidade`), então a busca por
unidade não passa pela busca textual — nem precisa, porque o filtro é exato.

**Toda oportunidade devolvida é da plataforma escolhida e tem
`link_plataforma` garantido** (decisão de produto, 28/08/2026): oportunidade
sem link de disputa não serve pra quem vai vender — melhor não existir. Hoje
a única plataforma registrada é o compras.gov.br (`plataforma_padrao()`);
quando houver mais de uma, o parâmetro `plataforma_id` (já aceito abaixo)
vira um dropdown na tela, como o de modalidade. Como o PNCP agrega TODAS as
plataformas (medido ao vivo: só ~11 de 50 editais de "café" eram do
Comprasnet), a busca textual detalha cada edital
(`PncpClient.detalhar_compra` -> `linkSistemaOrigem`) e descarta o que não é
da plataforma escolhida — e cai na reserva de catálogo (que já é 100%
compras.gov.br) quando a página não trouxe nenhum edital dela.

Portado do protótipo (branch `claude/tenta-de-novo-xu2sxb`, `app/oportunidades.py`),
já validado contra as APIs reais.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from django.core.cache import cache

from config.settings.environment import env

from apps.integracoes.clients.compras_gov import (
    MODALIDADE_CONTRATACOES_PARA_PNCP,
    MODALIDADES_CONTRATACOES,
    ComprasGovClient,
    ComprasGovClientError,
    montar_link_pncp,
    normalizar,
)
from apps.integracoes.clients.pncp import PncpClient, PncpClientError
from apps.integracoes.plataformas import PLATAFORMAS, Plataforma, identificar_plataforma, plataforma_padrao

logger = logging.getLogger(__name__)

MAX_CODIGOS_CATALOGO = 25  # códigos PDM inspecionados por busca
MAX_CONTRATACOES = 60  # teto de contratações no modo navegação
MAX_COMPRAS_DETALHADAS = 100  # teto de contratações detalhadas na busca por palavra
# Pendência de performance anotada em docs/DOMINIO.md: termo genérico ("cafe")
# levava ~2min, porque MAX_EDITAIS_PNCP editais viravam MAX_EDITAIS_PNCP
# chamadas de listar_itens, rodando em rodadas de MAX_WORKERS por vez. Editais
# reduzidos de 50 -> 20 e workers de 8 -> 20 deixa isso numa rodada só (contra
# ~7 antes), sem trocar o contrato da API nem da tela.
MAX_WORKERS = 20
MAX_EDITAIS_PNCP = 20  # teto de editais desdobrados em itens na busca textual
# Editais lidos da busca textual antes do filtro de plataforma (máximo que o
# portal aceita por página). Precisa ser maior que MAX_EDITAIS_PNCP porque a
# maioria dos editais do PNCP é de outras plataformas (medido ao vivo em
# 28/08/2026: ~11 de 50 eram do Comprasnet) — filtrar sobre 20 deixaria
# quase nada. Custo: até MAX_EDITAIS_BRUTOS chamadas de detalhe por busca,
# em paralelo (MAX_WORKERS por rodada).
MAX_EDITAIS_BRUTOS = 50

# Modalidade usada no modo navegação quando o usuário não escolhe nenhuma.
# "5" = Pregão Eletrônico NESTA tabela (MODALIDADES_CONTRATACOES em
# integracoes/clients/compras_gov.py) — não confundir com "6", que é o código
# do PNCP para a mesma modalidade. Usar o código errado aqui filtra
# silenciosamente por Dispensa (visto na prática: causava o link "abrir no
# compras.gov.br" sempre dar 404, porque Dispensa não tem sessão de disputa
# ao vivo).
MODALIDADE_PADRAO_NAVEGACAO = "5"


# O detalhe de uma compra não muda no que usamos dele (link de origem,
# esfera, código IBGE) — e o `/api/consulta/` do PNCP tem rate limit por IP
# (429, medido ao vivo em 28/08/2026, estourado por ~50 chamadas da rajada
# de uma busca). O cache faz buscas repetidas e o detalhe do card não
# pagarem de novo o que a busca já pagou. Backend padrão do Django é
# LocMem (por processo); apontar CACHES pra Redis no cluster estende o
# ganho pra todos os pods sem mudar este código.
CACHE_DETALHE_TTL = 6 * 60 * 60


def detalhar_compra_cacheada(
    cliente: PncpClient, *, cnpj: str, ano: str | int, sequencial: str | int
) -> dict[str, Any]:
    """`PncpClient.detalhar_compra` com cache. Erro não é cacheado — a
    próxima tentativa (fora da janela de rate limit) tenta de novo."""

    chave = f"pncp:detalhe:{cnpj}:{ano}:{sequencial}"
    detalhe = cache.get(chave)
    if detalhe is None:
        detalhe = cliente.detalhar_compra(cnpj=cnpj, ano=ano, sequencial=sequencial)
        cache.set(chave, detalhe, CACHE_DETALHE_TTL)
    return detalhe


class BuscaSemCorrespondenciaNoCatalogo(Exception):
    """A palavra-chave não casou com nenhum item do catálogo de materiais."""


def buscar_oportunidades(
    client: ComprasGovClient,
    *,
    data_inicial: str,
    data_final: str,
    codigo_modalidade: str = "",
    palavra_chave: str = "",
    codigos_pdm: list[int] | None = None,
    uf: str | None = None,
    codigo_unidade: str | None = None,
    pncp_client: PncpClient | None = None,
    plataforma_id: str = "",
) -> list[dict[str, Any]]:
    # Ponto de entrada do futuro dropdown de plataforma — id desconhecido ou
    # vazio cai na padrão (hoje a única: compras.gov.br).
    plataforma = PLATAFORMAS.get(plataforma_id) or plataforma_padrao()
    termo = palavra_chave.strip()
    unidade = (codigo_unidade or "").strip() or None
    if not termo:
        return _navegar_contratacoes(
            client,
            data_inicial=data_inicial,
            data_final=data_final,
            codigos_modalidade=_modalidades_da_navegacao(codigo_modalidade, unidade),
            uf=uf,
            codigo_unidade=unidade,
            plataforma=plataforma,
            pncp_client=pncp_client,
        )

    # Caminho preferido: busca textual do portal do PNCP.
    if env.usar_busca_pncp:
        try:
            resultados = _buscar_no_pncp(
                termo,
                data_inicial=data_inicial,
                data_final=data_final,
                codigo_modalidade=codigo_modalidade,
                uf=uf,
                codigo_unidade=unidade,
                pncp_client=pncp_client,
                plataforma=plataforma,
            )
        except PncpClientError as exc:
            # O endpoint não é documentado: se sumir ou mudar, a busca continua
            # pela reserva em vez de estourar na cara do usuário.
            logger.warning("Busca no PNCP falhou (%s); usando o índice de catálogo.", exc)
        else:
            # `None` = o PNCP não respondeu com editais; lista (mesmo vazia) = ele
            # respondeu, e a resposta vale — inclusive quando os filtros zeram.
            if resultados is not None:
                return resultados
            logger.info('Busca no PNCP não achou "%s"; tentando o índice de catálogo.', termo)

    # Reserva: códigos de PDM já resolvidos pela camada de busca do catálogo.
    if not codigos_pdm:
        raise BuscaSemCorrespondenciaNoCatalogo(palavra_chave)
    return _buscar_por_pdms(
        client,
        codigos_pdm=codigos_pdm,
        data_inicial=data_inicial,
        data_final=data_final,
        codigo_modalidade=codigo_modalidade,
        uf=uf,
        codigo_unidade=unidade,
        plataforma=plataforma,
    )


def _modalidades_da_navegacao(codigo_modalidade: str, codigo_unidade: str | None) -> list[str]:
    """Quais modalidades o modo navegação varre.

    Escolhida no dropdown, é ela e ponto. "Todas" (vazio) depende de haver
    UASG:

    - **Com UASG** (a busca por unidade da tela) varre as quatro modalidades
      que a API do compras.gov.br realmente devolve (`MODALIDADES_CONTRATACOES`
      — ver a varredura de 26/08/2026 em docs/DOMINIO.md). Uma unidade publica
      poucos editais por período, então são 4 listagens baratas — e é o que
      "Todas" promete. Antes daqui a busca por UASG caía no default de Pregão
      Eletrônico e escondia dispensa/inexigibilidade sem avisar, o que fazia a
      busca por unidade parecer quebrada (bug relatado pelo cliente).
    - **Sem UASG** o modo é varredura ampla do período inteiro: cada
      modalidade a mais multiplica MAX_CONTRATACOES chamadas de itens, então
      continua no default de Pregão Eletrônico — o caso de uso da tela.
      Ampliar isso é decisão de produto, não consequência desta correção.
    """

    if codigo_modalidade:
        return [codigo_modalidade]
    if codigo_unidade:
        return list(MODALIDADES_CONTRATACOES)
    return [MODALIDADE_PADRAO_NAVEGACAO]


def _buscar_no_pncp(
    termo: str,
    *,
    data_inicial: str,
    data_final: str,
    codigo_modalidade: str,
    uf: str | None,
    codigo_unidade: str | None,
    plataforma: Plataforma | None,
    pncp_client: PncpClient | None = None,
) -> list[dict[str, Any]] | None:
    """Busca editais pelo texto no PNCP, fica só com os da plataforma
    escolhida e desdobra cada um em oportunidades. `plataforma=None` = todas
    as plataformas (o Radar, GEN-68: "em todos os portais").

    Devolve `None` quando vale tentar o índice de catálogo: a busca não achou
    edital nenhum, OU achou mas nenhum é da plataforma escolhida (o PNCP
    agrega todas — e o catálogo indexa outra coisa e só acha compra do
    compras.gov.br, então pode achar o que aqui não sobrou). Devolve lista
    quando os filtros do usuário (UF/unidade/período) é que zeraram: filtro
    restritivo é resposta, não ausência de resposta — disparar a reserva aí
    seria uma segunda busca inútil.
    """

    proprio = pncp_client is None
    cliente = pncp_client or PncpClient()
    try:
        editais, _ = cliente.buscar_editais(
            termo,
            tamanho_pagina=MAX_EDITAIS_BRUTOS,
            uf=uf,
            # Traduzido: o código vem na tabela de `MODALIDADES_CONTRATACOES`
            # (dropdown do frontend / compras.gov.br), mas este endpoint
            # espera a tabela `MODALIDADES` do PNCP — ver comentário na
            # tradução. Código desconhecido (não deveria acontecer, o
            # dropdown só manda os 4 mapeados) cai em "sem filtro" em vez de
            # filtrar errado.
            codigo_modalidade=MODALIDADE_CONTRATACOES_PARA_PNCP.get(codigo_modalidade)
            if codigo_modalidade
            else None,
        )
        if not editais:
            return None

        # Sem cnpj/ano/sequencial não há como detalhar (nem, portanto,
        # descobrir a plataforma e o link de disputa) — e sem link não
        # existe oportunidade.
        editais = [
            e
            for e in editais
            if e.get("cnpj_orgao") and e.get("ano_compra") and e.get("sequencial_compra")
        ]
        if codigo_unidade:
            editais = [e for e in editais if (e.get("uasg") or "") == codigo_unidade]
        editais = [e for e in editais if _publicado_no_periodo(e, data_inicial, data_final)]
        if not editais:
            return []

        editais = _apenas_da_plataforma(cliente, editais, plataforma)
        if not editais:
            logger.info(
                'Busca no PNCP achou "%s", mas nenhum edital é de %s; tentando o catálogo.',
                termo,
                plataforma.nome if plataforma else "plataforma conhecida",
            )
            return None
        editais = editais[:MAX_EDITAIS_PNCP]

        def itens_seguros(edital: dict[str, Any]) -> list[dict[str, Any]]:
            try:
                return cliente.listar_itens(
                    cnpj=edital["cnpj_orgao"],
                    ano=edital["ano_compra"],
                    sequencial=edital["sequencial_compra"],
                )
            except PncpClientError:
                logger.warning("Falha ao listar itens do edital %s", edital.get("numero_controle_pncp"))
                return []

        oportunidades: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            for edital, itens in zip(editais, pool.map(itens_seguros, editais)):
                oportunidades.extend(_itens_relevantes(edital, itens, termo, plataforma))
        return oportunidades
    finally:
        if proprio:
            cliente.close()


def _apenas_da_plataforma(
    cliente: PncpClient, editais: list[dict[str, Any]], plataforma: Plataforma | None
) -> list[dict[str, Any]]:
    """Detalha cada edital no PNCP e fica só com os da plataforma escolhida,
    gravando neles o `link_plataforma` definitivo (`linkSistemaOrigem`) e os
    insumos do selo CAPAG (esfera + código IBGE).

    É o filtro caro da busca (1 chamada de detalhe por edital, em paralelo),
    mas é o único jeito: a resposta da busca textual não diz de qual
    plataforma o edital é (ver docs/DOMINIO.md, achado de 28/08/2026).
    Detalhe que falhar = edital descartado: sem link não existe oportunidade.

    Guardar os insumos do CAPAG aqui não é otimização opcional: o
    `/api/consulta/` do PNCP tem rate limit por IP (429, medido ao vivo em
    28/08/2026), e esta rajada o consome — a chamada de detalhe que o card
    dispara logo depois é justamente a que leva 429. Reaproveitar o detalhe
    que a busca já pagou é o que mantém o selo CAPAG aparecendo.
    """

    def detalhe_seguro(edital: dict[str, Any]) -> dict[str, Any] | None:
        try:
            return detalhar_compra_cacheada(
                cliente,
                cnpj=edital["cnpj_orgao"],
                ano=edital["ano_compra"],
                sequencial=edital["sequencial_compra"],
            )
        except PncpClientError:
            logger.warning(
                "Falha ao detalhar o edital %s", edital.get("numero_controle_pncp")
            )
            return None

    selecionados = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        for edital, detalhe in zip(editais, pool.map(detalhe_seguro, editais)):
            link = (detalhe or {}).get("link_plataforma")
            if not link or (plataforma is not None and not plataforma.pertence(link)):
                continue
            edital["link_plataforma"] = link
            edital["capag_esfera_id"] = detalhe.get("esfera_id")
            edital["capag_codigo_ibge"] = detalhe.get("codigo_ibge")
            selecionados.append(edital)
    return selecionados


def _publicado_no_periodo(edital: dict[str, Any], inicial: str, final: str) -> bool:
    """Aplica o período da tela ao resultado da busca textual.

    O buscador do portal filtra por situação ("recebendo proposta"), não por
    faixa de data, então o recorte é feito aqui. É deliberadamente tolerante:
    edital sem data de publicação legível **fica**.
    """

    publicacao = edital.get("data_publicacao")
    if not publicacao:
        return True
    if inicial and publicacao < inicial:
        return False
    if final and publicacao > final:
        return False
    return True


def _itens_relevantes(
    edital: dict[str, Any], itens: list[dict[str, Any]], termo: str, plataforma: Plataforma | None
) -> list[dict[str, Any]]:
    """Prioriza os itens que citam a palavra; se nenhum cita, devolve todos."""

    alvo = normalizar(termo)
    if not itens:
        return [_montar_oportunidade(edital, {}, plataforma)]

    casam = [
        i
        for i in itens
        if alvo in normalizar(f"{i.get('descricao_resumida') or ''} {i.get('descricao_detalhada') or ''}")
    ]
    return [_montar_oportunidade(edital, i, plataforma) for i in (casam or itens)]


def _buscar_por_pdms(
    client: ComprasGovClient,
    *,
    codigos_pdm: list[int],
    data_inicial: str,
    data_final: str,
    codigo_modalidade: str,
    uf: str | None,
    codigo_unidade: str | None,
    plataforma: Plataforma,
) -> list[dict[str, Any]]:
    def itens_do_pdm(codigo: int) -> list[dict[str, Any]]:
        try:
            return client.buscar_itens_por_pdm(
                codigo_pdm=codigo,
                data_inicial=data_inicial,
                data_final=data_final,
            )
        except ComprasGovClientError:
            logger.warning("Falha ao buscar itens do PDM %s", codigo)
            return []

    itens: list[dict[str, Any]] = []
    vistos: set[tuple] = set()
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        for lote in pool.map(itens_do_pdm, codigos_pdm[:MAX_CODIGOS_CATALOGO]):
            for item in lote:
                chave = (item.get("id_compra"), item.get("id_compra_item"), item.get("numero_item"))
                if chave in vistos:
                    continue
                vistos.add(chave)
                itens.append(item)

    if not itens:
        return []

    ids_compra = list(dict.fromkeys(i["id_compra"] for i in itens if i.get("id_compra")))
    contratacoes = _detalhar_em_paralelo(client, ids_compra[:MAX_COMPRAS_DETALHADAS])

    oportunidades = []
    for item in itens:
        contratacao = contratacoes.get(item.get("id_compra"))
        # Sem contratação ou sem id_compra não há link de disputa — e sem
        # link não existe oportunidade.
        if not contratacao or not contratacao.get("id_compra"):
            continue
        if not _passa_nos_filtros(contratacao, codigo_modalidade, uf, codigo_unidade):
            continue
        oportunidades.append(_montar_oportunidade(contratacao, item, plataforma))

    return oportunidades


def _navegar_contratacoes(
    client: ComprasGovClient,
    *,
    data_inicial: str,
    data_final: str,
    codigos_modalidade: list[str],
    uf: str | None,
    codigo_unidade: str | None,
    plataforma: Plataforma,
    pncp_client: PncpClient | None = None,
) -> list[dict[str, Any]]:
    """Lista as contratações do período (uma listagem por modalidade, em
    paralelo) e desdobra cada uma em itens.

    É o caminho da busca por UASG e da navegação sem palavra-chave. O
    `codigoModalidade` do compras.gov.br é obrigatório e aceita **um** código
    por chamada (sem ele a API responde 404), por isso "Todas" vira N
    listagens — ver `_modalidades_da_navegacao` para quando isso acontece.

    Os **itens** vêm do PNCP, não do compras.gov.br — ver `_itens_da_compra`.
    """

    def listar_seguro(
        codigo_modalidade: str,
    ) -> tuple[list[dict[str, Any]], ComprasGovClientError | None]:
        """Devolve (contratações, erro) — a falha vira dado em vez de subir na
        hora, para que uma modalidade fora do ar não zere as outras."""

        try:
            contratacoes, _ = client.buscar_contratacoes(
                data_publicacao_inicial=data_inicial,
                data_publicacao_final=data_final,
                codigo_modalidade=codigo_modalidade,
                uf=uf,
                codigo_unidade=codigo_unidade,
                tamanho_pagina=MAX_CONTRATACOES,
            )
        except ComprasGovClientError as exc:
            logger.warning("Falha ao listar contratações da modalidade %s", codigo_modalidade)
            return [], exc
        return [c for c in contratacoes if c.get("id_compra")], None

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        respostas = list(pool.map(listar_seguro, codigos_modalidade))
    # Nenhuma modalidade respondeu = a API está fora, não "nada encontrado":
    # o erro sobe e a view devolve 502, em vez de mentir uma tela vazia.
    erros = [erro for _, erro in respostas if erro is not None]
    if erros and len(erros) == len(respostas):
        raise erros[0]
    por_modalidade = [contratacoes for contratacoes, _ in respostas]
    # Intercalado, não concatenado: o teto de MAX_CONTRATACOES é global, e
    # concatenar deixaria a primeira modalidade consumir a cota sozinha —
    # a busca por UASG voltaria a esconder dispensa/inexigibilidade.
    candidatas = _intercalar(por_modalidade)[:MAX_CONTRATACOES]

    # Só abre client de PNCP se for usar (e fecha o que abriu) — quem chama
    # de fora pode passar o dele, e é o que os testes fazem pra não sair na rede.
    usar_pncp = env.usar_busca_pncp
    proprio = usar_pncp and pncp_client is None
    cliente_pncp = (pncp_client or PncpClient()) if usar_pncp else None

    def itens_seguros(contratacao: dict[str, Any]) -> list[dict[str, Any]]:
        return _itens_da_compra(client, cliente_pncp, contratacao)

    try:
        oportunidades = []
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            for contratacao, itens in zip(candidatas, pool.map(itens_seguros, candidatas)):
                # Contratação sem item publicado ainda vira card: dá pra abrir
                # o edital e a disputa na plataforma. Mesmo tratamento que a
                # busca textual dá (ver `_itens_relevantes`) — sumir com a
                # contratação seria pior que mostrá-la sem a lista de itens.
                for item in itens or [{}]:
                    oportunidades.append(_montar_oportunidade(contratacao, item, plataforma))
    finally:
        if proprio and cliente_pncp is not None:
            cliente_pncp.close()

    return oportunidades


def _itens_da_compra(
    client: ComprasGovClient,
    pncp: PncpClient | None,
    contratacao: dict[str, Any],
) -> list[dict[str, Any]]:
    """Itens de uma contratação, **do PNCP primeiro**, com o compras.gov.br
    como reserva.

    Achado de 06/09/2026, medido ao vivo: o mirror de *itens* do
    compras.gov.br (`2.1_consultarItensContratacoes...`) está muito mais
    atrasado que o de *contratações*. Contratação publicada até 02/09 já
    aparece na listagem; os itens dela só existem para o que foi publicado
    até ~24/07 — de 01/08 em diante o endpoint responde `resultado: []`, sem
    erro. Como este caminho só produzia oportunidade a partir de item, a
    navegação e a busca por UASG voltavam **vazias para qualquer edital
    recente** (era o "a busca por UASG não funciona" relatado pelo cliente).

    O PNCP não tem essa defasagem — é a mesma fonte de itens que a busca
    textual já usa. A reserva no compras.gov.br continua valendo para o
    período antigo e para quando o PNCP está fora do ar (ele cai bastante,
    ver `PncpClient`).
    """

    identificado = all(
        contratacao.get(campo) for campo in ("cnpj_orgao", "ano_compra", "sequencial_compra")
    )
    if pncp is not None and identificado:
        try:
            itens = pncp.listar_itens(
                cnpj=contratacao["cnpj_orgao"],
                ano=contratacao["ano_compra"],
                sequencial=contratacao["sequencial_compra"],
            )
        except PncpClientError:
            logger.warning(
                "Falha ao buscar itens no PNCP da compra %s", contratacao.get("id_compra")
            )
        else:
            if itens:
                return itens

    if not contratacao.get("id_compra"):
        return []
    try:
        return client.listar_itens(contratacao["id_compra"])
    except ComprasGovClientError:
        logger.warning("Falha ao buscar itens da compra %s", contratacao.get("id_compra"))
        return []


def _intercalar(listas: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Uma de cada lista, em rodadas, até acabarem — mantém a ordem relativa
    dentro de cada lista e dá a mesma chance a todas quando o resultado é
    cortado por um teto."""

    intercalada: list[dict[str, Any]] = []
    for posicao in range(max((len(lista) for lista in listas), default=0)):
        for lista in listas:
            if posicao < len(lista):
                intercalada.append(lista[posicao])
    return intercalada


def _detalhar_em_paralelo(
    client: ComprasGovClient, ids_compra: list[str]
) -> dict[str, dict[str, Any]]:
    def detalhar(id_compra: str) -> tuple[str, dict[str, Any] | None]:
        try:
            return id_compra, client.detalhar_contratacao(id_compra)
        except ComprasGovClientError:
            logger.warning("Falha ao detalhar a compra %s", id_compra)
            return id_compra, None

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        return {id_: c for id_, c in pool.map(detalhar, ids_compra) if c}


def _passa_nos_filtros(
    contratacao: dict[str, Any],
    codigo_modalidade: str,
    uf: str | None,
    codigo_unidade: str | None,
) -> bool:
    if uf and (contratacao.get("uf") or "").upper() != uf.upper():
        return False
    if codigo_unidade and (contratacao.get("uasg") or "") != codigo_unidade:
        return False
    if codigo_modalidade and str(contratacao.get("codigo_modalidade") or "") != str(codigo_modalidade):
        return False
    return True


def _montar_oportunidade(
    contratacao: dict[str, Any], item: dict[str, Any], plataforma: Plataforma | None
) -> dict[str, Any]:
    # Toda oportunidade tem link de disputa garantido: no caminho da busca
    # textual ele já veio gravado na contratação (`linkSistemaOrigem`, ver
    # `_apenas_da_plataforma`); nos caminhos do compras.gov.br
    # (navegação/PDM) a própria plataforma o monta do `id_compra` — e quem
    # chega aqui sem id_compra já foi descartado antes.
    if plataforma is None:
        # Todas as plataformas (Radar): a do link, se registrada; senão vazio
        # — o link de origem continua valendo (ver `plataformas.py`).
        plataforma = identificar_plataforma(contratacao.get("link_plataforma"))
    link_plataforma = contratacao.get("link_plataforma") or (
        plataforma.montar_link(contratacao) if plataforma else None
    )
    internos = {"raw_json", "link_plataforma", "capag_esfera_id", "capag_codigo_ibge"}
    return {
        **{f"contratacao_{k}": v for k, v in contratacao.items() if k not in internos},
        # Insumos do selo CAPAG, quando a busca já os pagou (caminho da busca
        # textual). Quem resolve nota é a view — services não toca em banco.
        "capag_esfera_id": contratacao.get("capag_esfera_id"),
        "capag_codigo_ibge": contratacao.get("capag_codigo_ibge"),
        "numero_item": item.get("numero_item"),
        "descricao_resumida": item.get("descricao_resumida"),
        "descricao_detalhada": item.get("descricao_detalhada"),
        "material_ou_servico": item.get("material_ou_servico"),
        "quantidade": item.get("quantidade"),
        "unidade_medida": item.get("unidade_medida"),
        "valor_unitario_estimado": item.get("valor_unitario_estimado"),
        "valor_total": item.get("valor_total"),
        "situacao_item": item.get("situacao"),
        "criterio_julgamento": item.get("criterio_julgamento"),
        "tipo_beneficio": item.get("tipo_beneficio"),
        "plataforma_id": plataforma.id if plataforma else "",
        "link_plataforma": link_plataforma,
        "link_pncp": montar_link_pncp(contratacao),
    }
