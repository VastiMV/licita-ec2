"""Salvar uma oportunidade na lista da equipe — a regra, num lugar só.

Existem dois caminhos até aqui e eles precisam se comportar igual:

1. o botão "Salvar oportunidade" do card (`OportunidadesSalvasView.post`);
2. salvar uma cotação no Cotador, que salva a oportunidade junto — é o
   único jeito de a equipe voltar a ela depois (ver
   `apps.cotador.views.CotacoesView`).

O que os dois compartilham é a idempotência: salvar de novo o que já está
na lista devolve o registro existente e **não** cria evento no histórico —
um clique repetido (ou um segundo salvamento de cotação) não pode virar
ruído no log. A exceção (10/11/2026): quando o salvar de novo **muda**
alguma coisa — completa campos vazios de uma salva que a Sentinela trouxe,
ou é a primeira pessoa a salvá-la — fica um evento dizendo o quê.
"""

from __future__ import annotations

from .models import EventoOportunidadeSalva, OportunidadeSalva, montar_texto_busca, nome_de_usuario
from .serializers import OportunidadeSalvaCriacaoSerializer


def garantir_salva(dados: dict, *, request) -> tuple[OportunidadeSalva, bool]:
    """Salva a oportunidade descrita por `dados` (o payload de
    `OportunidadeSalvaCriacaoSerializer`: os itens da busca + capag +
    plataforma) e devolve `(registro, criada)`.

    Levanta `ValidationError` do DRF quando o payload não identifica a
    compra no PNCP — sem a tripla não há como impedir duplicata.
    """

    serializer = OportunidadeSalvaCriacaoSerializer(data=dados, context={"request": request})
    serializer.is_valid(raise_exception=True)

    contratacao = serializer.validated_data["itens"][0]
    existente = (
        OportunidadeSalva.objects.ativas()
        .filter(
            cnpj_orgao=contratacao["contratacao_cnpj_orgao"],
            ano_compra=contratacao["contratacao_ano_compra"],
            sequencial_compra=contratacao["contratacao_sequencial_compra"],
        )
        .first()
    )
    if existente:
        _completar_com_a_busca(existente, serializer.validated_data, request)
        return existente, False

    salva = serializer.save()
    salva.registrar(
        EventoOportunidadeSalva.Tipo.SALVA,
        autor=request.user,
        descricao=f"Oportunidade salva por {nome_de_usuario(request.user)}.",
    )
    return salva, True


def _completar_com_a_busca(salva: OportunidadeSalva, dados: dict, request) -> None:
    """A salva já existia — em geral trazida pela Sentinela, que grava só o
    que o Compras.gov manda (sem itens, às vezes sem o órgão). Quem salva
    pela busca tem os dados completos do PNCP: eles preenchem **só o que está
    vazio** (10/11/2026, Dispensa 27/2026 das ararinhas).

    Continua idempotente: só há evento quando algo muda — a primeira pessoa
    a salvar uma que a Sentinela trouxe, ou dados que faltavam."""

    from .serializers import _valor_total

    itens = dados["itens"]
    contratacao = itens[0]
    novos = {
        "orgao_nome": contratacao.get("contratacao_orgao_nome"),
        "uasg": contratacao.get("contratacao_uasg"),
        "uf": contratacao.get("contratacao_uf"),
        "municipio": contratacao.get("contratacao_municipio"),
        "objeto": contratacao.get("contratacao_objeto"),
        "modalidade": contratacao.get("contratacao_modalidade"),
        "situacao": contratacao.get("contratacao_situacao"),
        "link_pncp": contratacao.get("link_pncp"),
    }
    preenchidos = []
    for campo, valor in novos.items():
        valor = (valor or "").strip()
        if valor and not getattr(salva, campo):
            limite = OportunidadeSalva._meta.get_field(campo).max_length
            setattr(salva, campo, valor[:limite] if limite else valor)
            preenchidos.append(campo)
    if not salva.itens:
        salva.itens = itens
        preenchidos.append("itens")
    if salva.valor_total_estimado is None and (total := _valor_total(itens)) is not None:
        salva.valor_total_estimado = total
        preenchidos.append("valor_total_estimado")
    if salva.capag is None and dados.get("capag"):
        salva.capag = dados["capag"]
        preenchidos.append("capag")

    primeira_pessoa = salva.salva_por_id is None and getattr(request.user, "is_authenticated", False)
    if primeira_pessoa:
        salva.salva_por = request.user
        # `salva_por_nome` é gravado pelo pre_save de `accounts.autoria`.
        preenchidos += ["salva_por", "salva_por_nome"]
    if not preenchidos:
        return
    if "itens" in preenchidos or "objeto" in preenchidos:
        salva.texto_busca = montar_texto_busca(salva.objeto, salva.itens)
        preenchidos.append("texto_busca")
    salva.save(update_fields=preenchidos)

    completados = [c for c in preenchidos if c not in {"salva_por", "salva_por_nome", "texto_busca"}]
    quem = nome_de_usuario(request.user)
    if primeira_pessoa:
        descricao = f"Oportunidade salva por {quem} (já estava na lista)."
    else:
        descricao = f"{quem} salvou de novo pela busca."
    if completados:
        descricao += " Dados completados pela busca: " + ", ".join(completados) + "."
    salva.registrar(
        EventoOportunidadeSalva.Tipo.SALVA if primeira_pessoa else EventoOportunidadeSalva.Tipo.CORRECAO,
        autor=request.user if getattr(request.user, "is_authenticated", False) else None,
        descricao=descricao,
        dados={"campos": completados},
    )
