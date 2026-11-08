"""Oportunidades salvas e o histórico (log) de cada uma.

A busca de oportunidades continua sem persistir nada (ver `services.py` e
docs/DOMINIO.md) — o que persiste é o que alguém **escolheu salvar**, e é
sempre um *edital/compra* inteiro (o card), nunca um item solto.

Duas decisões de produto moldam estes models:

**A lista é da empresa, não do usuário.** Quem salva fica registrado
(`salva_por`), mas a oportunidade salva aparece para todos os usuários — o
time trabalha a mesma lista. Por isso não há filtro por `owner` nas
consultas, e a unicidade é global (uma compra salva não pode entrar duas
vezes na lista).

**Excluir da lista não apaga o histórico.** O log precisa poder dizer "foi
removida por fulano" *depois* da remoção, então excluir é remoção lógica
(`removida_em`/`removida_por`): a linha sai da lista, os eventos ficam. A
unicidade é condicionada a `removida_em IS NULL` justamente para permitir
salvar de novo depois — o que cria um registro novo, com log próprio, sem
misturar com a história do anterior.

O status "expirada" (prazo de proposta vencido) é **calculado**, nunca
gravado — ver `OportunidadeSalvaQuerySet.expiradas`. O que se grava é o
*evento* de que o prazo passou (uma vez só, ver `registrar_prazos_vencidos`),
porque isso é história e não muda mais depois.
"""

from __future__ import annotations

import datetime as dt

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class OportunidadeSalvaQuerySet(models.QuerySet):
    def ativas(self) -> "OportunidadeSalvaQuerySet":
        """As que estão na lista — remoção é lógica (ver docstring do módulo)."""

        return self.filter(removida_em__isnull=True)

    def sem_cotacao(self) -> "OportunidadeSalvaQuerySet":
        """As que ainda estão na etapa Oportunidade do Ciclo de Licitação.
        Com cotação salva, a licitação passou para a etapa Cotação e sai da
        lista de Salvas (ver `ciclo.py`)."""

        return self.filter(cotacao__isnull=True)

    def sem_proposta(self) -> "OportunidadeSalvaQuerySet":
        """Ainda não chegaram à etapa Proposta (ver `apps.propostas`)."""

        return self.filter(proposta__isnull=True)

    def expiradas(self, hoje: dt.date | None = None) -> "OportunidadeSalvaQuerySet":
        """Prazo de proposta já vencido. Sem data de encerramento = não expira
        (o PNCP nem sempre publica a data; sem ela não dá pra afirmar que
        venceu)."""

        return self.filter(data_encerramento_proposta__lt=hoje or timezone.localdate())

    def no_prazo(self, hoje: dt.date | None = None) -> "OportunidadeSalvaQuerySet":
        """O contrário de `expiradas`: prazo aberto ou sem data publicada. Só
        estas estão em alguma etapa do ciclo; as outras saíram dele (ver
        `encerradas.py`: Descartadas, ou Encerradas quando participou)."""

        return self.exclude(data_encerramento_proposta__lt=hoje or timezone.localdate())

    def buscar(self, termo: str) -> "OportunidadeSalvaQuerySet":
        """Busca textual da tabela — casa no objeto do edital e na descrição
        dos itens, via `texto_busca` (ver `montar_texto_busca`)."""

        termo = (termo or "").strip()
        if not termo:
            return self
        return self.filter(texto_busca__contains=normalizar_busca(termo))


def normalizar_busca(texto: str) -> str:
    """Caixa alta e sem acento — mesma normalização dos dois lados da
    comparação, para "cafe" achar "CAFÉ"."""

    # Importado aqui (e não no topo) só para deixar explícito que a regra de
    # normalização é a mesma do resto do domínio, definida em integracoes.
    from apps.integracoes.clients.compras_gov import normalizar

    return normalizar(texto)


def montar_texto_busca(objeto: str, itens: list[dict]) -> str:
    """Campo denormalizado que a busca da tabela varre: objeto do edital +
    descrição dos itens, tudo normalizado. Denormalizado de propósito — a
    alternativa é varrer o JSON de `itens` a cada tecla digitada."""

    partes = [objeto or ""]
    for item in itens:
        partes.append(item.get("descricao_resumida") or "")
        partes.append(item.get("descricao_detalhada") or "")
    return normalizar_busca(" ".join(p for p in partes if p))


class OportunidadeSalva(models.Model):
    """Uma compra (edital) que alguém salvou para trabalhar depois.

    Os campos são um **snapshot** do que a busca devolveu: a lista e o modal
    de visualização renderizam sem consultar PNCP/compras.gov.br de novo. O
    que muda com o tempo (documentos do edital, plataforma de origem, selo
    CAPAG) não vem daqui — o frontend pede ao `CompraDetalheView`, que é
    cacheado, quando abre o modal.
    """

    # Identidade da compra no PNCP — mesma tripla que o frontend usa pra
    # agrupar itens num card só (`chaveEdital` em pesquisar.page.ts).
    cnpj_orgao = models.CharField("CNPJ do órgão", max_length=20)
    ano_compra = models.CharField("ano da compra", max_length=8)
    sequencial_compra = models.CharField("sequencial da compra", max_length=20)

    # Snapshot de exibição.
    objeto = models.TextField("objeto", blank=True)
    orgao_nome = models.CharField("órgão", max_length=255, blank=True)
    uasg = models.CharField("UASG", max_length=20, blank=True)
    uf = models.CharField("UF", max_length=2, blank=True)
    municipio = models.CharField("município", max_length=255, blank=True)
    modalidade = models.CharField("modalidade", max_length=120, blank=True)
    situacao = models.CharField("situação", max_length=120, blank=True)
    data_publicacao = models.DateField("publicada em", null=True, blank=True)
    data_encerramento_proposta = models.DateField(
        "propostas até", null=True, blank=True, help_text="Base do status 'expirada'."
    )
    valor_total_estimado = models.DecimalField(
        "valor estimado", max_digits=18, decimal_places=2, null=True, blank=True
    )

    plataforma_id = models.CharField(
        "plataforma",
        max_length=40,
        blank=True,
        help_text="Id do registro em apps/integracoes/plataformas.py.",
    )
    plataforma_nome = models.CharField("nome da plataforma", max_length=120, blank=True)
    link_plataforma = models.TextField("link na plataforma", blank=True)
    link_pncp = models.TextField("link no PNCP", blank=True)
    numero_processo = models.CharField(
        "nº do processo",
        max_length=60,
        blank=True,
        help_text="Processo administrativo do órgão — liga empenho e pagamento do Portal da Transparência à compra.",
    )

    capag = models.JSONField("selo CAPAG", null=True, blank=True)
    itens = models.JSONField(
        "itens (snapshot)",
        default=list,
        help_text="As linhas da busca deste edital, no formato de OportunidadeSerializer.",
    )
    # Sem índice de propósito: a consulta é substring ("contém"), que um
    # btree não serve — e um btree sobre texto longo ainda esbarra no limite
    # de tamanho de linha do Postgres. A lista de uma equipe cabe num scan
    # sequencial; se um dia não couber, o padrão a copiar é o do catálogo
    # (`Pdm`): GinIndex com `gin_trgm_ops`.
    texto_busca = models.TextField("texto de busca", blank=True)

    salva_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="salva por",
        related_name="oportunidades_salvas",
        null=True,
        on_delete=models.SET_NULL,
    )
    salva_por_nome = models.CharField(
        "salva por (nome)",
        max_length=150,
        blank=True,
        help_text="Gravado junto com o autor: o nome continua aqui se o usuário for excluído.",
    )
    criada_em = models.DateTimeField("salva em", auto_now_add=True)

    removida_em = models.DateTimeField("removida em", null=True, blank=True)
    removida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="removida por",
        related_name="oportunidades_removidas",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    removida_por_nome = models.CharField(
        "removida por (nome)",
        max_length=150,
        blank=True,
        help_text="Gravado junto com o autor: o nome continua aqui se o usuário for excluído.",
    )

    objects = OportunidadeSalvaQuerySet.as_manager()

    class Meta:
        verbose_name = "oportunidade salva"
        verbose_name_plural = "oportunidades salvas"
        ordering = ["-criada_em"]
        constraints = [
            # Só entre as ativas: remover e salvar de novo é permitido (e
            # gera um registro novo, com log próprio).
            models.UniqueConstraint(
                fields=["cnpj_orgao", "ano_compra", "sequencial_compra"],
                condition=Q(removida_em__isnull=True),
                name="oportunidade_salva_unica_por_compra_ativa",
            )
        ]

    def __str__(self) -> str:
        return f"{self.chave} — {self.resumo}"

    @property
    def chave(self) -> str:
        """Mesma chave do card na busca — é por ela que o frontend sabe que
        uma oportunidade da busca já está salva."""

        return f"{self.cnpj_orgao}-{self.ano_compra}-{self.sequencial_compra}"

    @property
    def resumo(self) -> str:
        """Descrição curta usada no log (o registro principal do histórico
        mostra "oportunidade X, com a descrição Y")."""

        objeto = " ".join((self.objeto or "").split())
        return objeto[:117] + "…" if len(objeto) > 118 else objeto or "sem objeto informado"

    def expirada(self, hoje: dt.date | None = None) -> bool:
        """Prazo de proposta vencido sem proposta gerada — o que tira a
        licitação do ciclo. Com proposta, o prazo vencer é o caminho normal."""

        if not self.data_encerramento_proposta or hasattr(self, "proposta"):
            return False
        return self.data_encerramento_proposta < (hoje or timezone.localdate())

    def registrar(
        self,
        tipo: "EventoOportunidadeSalva.Tipo",
        *,
        autor=None,
        descricao: str = "",
        dados: dict | None = None,
    ) -> "EventoOportunidadeSalva":
        """Acrescenta uma linha ao histórico desta oportunidade."""

        return EventoOportunidadeSalva.objects.create(
            oportunidade=self,
            tipo=tipo,
            autor=autor,
            descricao=descricao or EventoOportunidadeSalva.Tipo(tipo).label,
            dados=dados or {},
        )

    def remover(self, *, por=None, quando: dt.datetime | None = None) -> None:
        """Tira da lista sem apagar a história (ver docstring do módulo)."""

        self.removida_em = quando or timezone.now()
        self.removida_por = por
        self.save(update_fields=["removida_em", "removida_por", "removida_por_nome"])
        self.registrar(
            EventoOportunidadeSalva.Tipo.REMOVIDA,
            autor=por,
            descricao=(
                f"Removida da lista por {nome_de_usuario(por)}."
                if por
                else "Removida da lista."
            ),
        )


def registrar_prazos_vencidos(hoje: dt.date | None = None) -> int:
    """Grava o evento "prazo de proposta vencido" nas salvas que passaram do
    prazo e ainda não têm esse evento. Devolve quantas foram registradas.

    Chamado quando a lista é servida, e não por uma task periódica: o status
    em si é calculado (não precisa de task pra ficar correto), e o log só
    precisa da linha antes de alguém olhar o histórico. Idempotente — a
    exclusão pelo tipo do evento garante uma linha só por oportunidade.
    """

    vencidas = (
        OportunidadeSalva.objects.ativas()
        .sem_proposta()
        .expiradas(hoje)
        .exclude(eventos__tipo=EventoOportunidadeSalva.Tipo.PRAZO_VENCIDO)
    )
    eventos = [
        EventoOportunidadeSalva(
            oportunidade=oportunidade,
            tipo=EventoOportunidadeSalva.Tipo.PRAZO_VENCIDO,
            descricao=(
                "Prazo para envio de proposta encerrado em "
                f"{oportunidade.data_encerramento_proposta:%d/%m/%Y}."
            ),
        )
        for oportunidade in vencidas
    ]
    EventoOportunidadeSalva.objects.bulk_create(eventos)
    return len(eventos)


def nome_de_usuario(usuario) -> str:
    return getattr(usuario, "nome", "") or getattr(usuario, "email", "") or "sistema"


class EventoOportunidadeSalva(models.Model):
    """Uma linha do histórico de uma oportunidade salva.

    O módulo que lê esse histórico ainda não existe (é a tela "detalhes" do
    registro principal, no estilo de um extrato de ligação); o log, porém, é
    escrito desde já — história não dá pra reconstruir depois.

    `tipo` é fechado de propósito: a tela do histórico agrupa/ícone por tipo,
    e um tipo novo (ex.: `PROPOSTA_GERADA`, já previsto aqui) entra junto com
    a funcionalidade que o produz. `dados` é o espaço livre para o que cada
    tipo precisa carregar — é dele que sai o link de "abrir a proposta"
    quando esse módulo existir (`{"proposta_id": 42}`), sem migração nova.
    """

    class Tipo(models.TextChoices):
        SALVA = "salva", "Oportunidade salva"
        PRAZO_VENCIDO = "prazo_vencido", "Prazo de proposta encerrado"
        REMOVIDA = "removida", "Removida da lista"
        # Nome histórico: é o salvar da cotação (o valor gravado não muda,
        # o histórico já está escrito com ele).
        PROPOSTA_GERADA = "proposta_gerada", "Cotação salva"
        # Gerar proposta no Cotador (`apps.propostas`).
        PROPOSTA = "proposta", "Proposta gerada"
        # A lixeira da Torre (08/11/2026): quem, quando, em que etapa e com
        # que preço — a operação esquece e pergunta depois.
        DESCARTADA = "descartada", "Descartada manualmente"
        # Descartada que voltou sozinha porque houve convocação.
        VOLTOU = "voltou", "Voltou para a Torre"

    oportunidade = models.ForeignKey(
        OportunidadeSalva,
        verbose_name="oportunidade",
        related_name="eventos",
        on_delete=models.CASCADE,
    )
    tipo = models.CharField("tipo", max_length=32, choices=Tipo.choices)
    descricao = models.TextField("descrição", help_text="Texto pronto para exibição no histórico.")
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="autor",
        related_name="eventos_de_oportunidade",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="Nulo = evento do sistema (ex.: prazo vencido).",
    )
    autor_nome = models.CharField(
        "autor (nome)",
        max_length=150,
        blank=True,
        help_text="Gravado junto com o autor: o nome continua aqui se o usuário for excluído.",
    )
    dados = models.JSONField("dados", default=dict, blank=True)
    ocorrido_em = models.DateTimeField("ocorrido em", auto_now_add=True)

    class Meta:
        verbose_name = "evento de oportunidade salva"
        verbose_name_plural = "eventos de oportunidade salva"
        ordering = ["ocorrido_em", "id"]

    def __str__(self) -> str:
        return f"{self.ocorrido_em:%d/%m/%Y %H:%M} — {self.descricao}"


# ---------------------------------------------------------------------------
# Torre de Controle — o que acontece depois de cotar
#
# Os quatro models abaixo guardam **fatos** vindos de fora (Compras.gov.br
# pela Sentinela, PNCP, Portal da Transparência) ou lançados à mão. A etapa
# continua calculada (ver `torre.py`): ninguém grava "esta licitação está em
# Habilitação"; grava-se que a proposta do item 22 foi aceita, e a etapa sai
# disso. Ver docs/Tarefas/feat-torre-de-controle.md.
# ---------------------------------------------------------------------------


class Fonte(models.TextChoices):
    """De onde veio o fato — para saber em quem confiar quando duas fontes
    discordam e para mostrar "lido pela Sentinela às 14h"."""

    SENTINELA = "sentinela", "Sentinela (Compras.gov.br)"
    PNCP = "pncp", "PNCP"
    TRANSPARENCIA = "transparencia", "Portal da Transparência"
    MANUAL = "manual", "Lançado à mão"


class ParticipacaoCompra(models.Model):
    """O que o Compras.gov.br diz da compra para a empresa.

    Os códigos são os do próprio Compras.gov.br (`comprasnet-fase-externa/v1/
    enums`), gravados como vêm: traduzir na leitura deixa o fato fiel à fonte
    e a tradução num lugar só (`torre.py`).
    """

    class Situacao(models.TextChoices):
        PUBLICADA = "PD", "Publicada"
        SUSPENSA = "SU", "Suspensa"
        REVOGADA = "RE", "Revogada"
        ANULADA = "AN", "Anulada"
        FRACASSADA = "FR", "Fracassada"
        DESERTA = "DE", "Deserta"

    oportunidade = models.OneToOneField(
        OportunidadeSalva,
        verbose_name="oportunidade",
        related_name="participacao",
        on_delete=models.CASCADE,
    )
    fase_compra = models.CharField(
        "fase da compra",
        max_length=4,
        blank=True,
        help_text="FaseCompraFaseExterna: 1 aguardando abertura, 99 disputa agendada, 3 disputa, 4 seleção de fornecedores.",
    )
    situacao_compra = models.CharField(
        "situação da compra", max_length=2, choices=Situacao.choices, blank=True
    )
    proposta_cadastrada = models.BooleanField(
        "proposta cadastrada",
        null=True,
        blank=True,
        help_text="Nulo = ainda não se sabe (a Sentinela não leu).",
    )
    diligencia_em_andamento = models.BooleanField("diligência em andamento", default=False)
    convocacao_em_andamento = models.BooleanField("convocação em andamento", default=False)
    sessao_abre_em = models.DateTimeField("sessão abre em", null=True, blank=True)
    fonte = models.CharField("fonte", max_length=16, choices=Fonte.choices, default=Fonte.SENTINELA)
    atualizada_em = models.DateTimeField("atualizada em", auto_now=True)

    class Meta:
        verbose_name = "participação na compra"
        verbose_name_plural = "participações nas compras"

    def __str__(self) -> str:
        return f"Participação em {self.oportunidade}"


class ItemParticipado(models.Model):
    """Um item da compra em que a empresa tem proposta.

    A etapa da licitação é a do item mais adiantado (ver `torre.py`), por
    isso o fato mora aqui, no item, e não na compra.
    """

    class SituacaoProposta(models.TextChoices):
        # SituacaoPropostaItemEnum do Compras.gov.br. 1, 2 e 9 são todas
        # "desclassificada" na origem; guardamos o código como veio.
        DESCLASSIFICADA = "1", "Proposta desclassificada"
        DESCLASSIFICADA_2 = "2", "Proposta desclassificada"
        DESCLASSIFICADA_9 = "9", "Proposta desclassificada"
        ACEITA = "3", "Proposta aceita"
        HABILITADO = "4", "Fornecedor habilitado"
        INABILITADO = "5", "Fornecedor inabilitado"
        ADJUDICADA = "6", "Proposta adjudicada"
        PENDENTE_COTA = "7", "Pendente aceite para assumir cota"
        RECUSA_COTA = "8", "Recusa para assumir cota"

    oportunidade = models.ForeignKey(
        OportunidadeSalva,
        verbose_name="oportunidade",
        related_name="itens_participados",
        on_delete=models.CASCADE,
    )
    numero_item = models.CharField("nº do item", max_length=20, help_text='Como no edital: "22", "G2".')
    descricao = models.TextField("descrição", blank=True)
    quantidade = models.DecimalField("quantidade", max_digits=16, decimal_places=4, null=True, blank=True)
    marca = models.CharField("marca/fabricante", max_length=120, blank=True)
    modelo = models.CharField("modelo/versão", max_length=120, blank=True)

    classificacao = models.PositiveIntegerField("posição", null=True, blank=True)
    situacao_proposta = models.CharField(
        "situação da proposta", max_length=2, choices=SituacaoProposta.choices, blank=True
    )
    fase_item = models.CharField(
        "fase do item", max_length=4, blank=True, help_text="FaseItemEnum do Compras.gov.br (E, HE, AR, AE…)."
    )
    anexo_solicitado = models.CharField(
        "convocação de anexo",
        max_length=1,
        blank=True,
        help_text="S solicitada · P parcialmente encerrada · E encerrada · vazio = nunca pedida.",
    )
    recurso_ate = models.DateField("recurso aberto até", null=True, blank=True)
    negociacao = models.CharField(
        "negociação",
        max_length=1,
        blank=True,
        help_text="situacaoUltimaNegociacao do Compras.gov.br: E = encerrada; outro valor = em andamento "
        "(o pregoeiro pediu desconto e espera resposta). Vazio = nunca houve.",
    )
    negociacao_texto = models.TextField(
        "pedido do pregoeiro", blank=True, help_text='Ex.: "Solicito um desconto para o Item 22".'
    )

    # Fase recursal do item (`fase-recursal-fornecedor/<sessão>`, lida pela
    # Sentinela). Caso real: Pregão 56/2026, item 22 — recurso da Brava Sul que
    # ninguém viu a tempo de responder (08/11/2026).
    sessao_julgamento = models.PositiveSmallIntegerField(
        "sessão de julgamento", default=1, help_text="numeroSessaoJulgHab: entra no endereço da fase recursal."
    )
    recursos = models.JSONField(
        "recursos cadastrados",
        default=list,
        blank=True,
        help_text='[{"cnpj", "nome", "em"}] — quem entrou com recurso neste item.',
    )
    prazo_contrarrazao = models.DateTimeField("contrarrazões até", null=True, blank=True)
    decisao_recurso = models.CharField(
        "decisão do recurso",
        max_length=1,
        blank=True,
        help_text="SituacaoRecursalEnum: P procede · N não procede · M mantida (não procede) · R revertida. "
        "Vale a revisão da autoridade, se houver.",
    )
    diligencias_abertas = models.PositiveSmallIntegerField("diligências em aberto", default=0)

    valor_proposta_inicial = models.DecimalField(
        "proposta inicial (unitário)", max_digits=18, decimal_places=4, null=True, blank=True
    )
    valor_lance_final = models.DecimalField(
        "lance final (unitário)", max_digits=18, decimal_places=4, null=True, blank=True
    )
    valor_negociado = models.DecimalField(
        "negociado (unitário)", max_digits=18, decimal_places=4, null=True, blank=True
    )
    valor_homologado = models.DecimalField(
        "homologado (unitário)", max_digits=18, decimal_places=4, null=True, blank=True
    )
    homologado_em = models.DateField("homologado em", null=True, blank=True)
    vencedor_e_a_empresa = models.BooleanField(
        "a empresa venceu",
        null=True,
        blank=True,
        help_text="Do resultado do PNCP. Nulo = sem resultado; falso = homologado para outro fornecedor.",
    )

    fonte = models.CharField("fonte", max_length=16, choices=Fonte.choices, default=Fonte.SENTINELA)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "item participado"
        verbose_name_plural = "itens participados"
        ordering = ["oportunidade_id", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["oportunidade", "numero_item"], name="item_participado_unico_por_compra"
            )
        ]

    def __str__(self) -> str:
        return f"Item {self.numero_item} de {self.oportunidade}"


class DocumentoFinanceiro(models.Model):
    """Contrato, ata, empenho, ordem de fornecimento, liquidação ou pagamento.

    Vários do mesmo tipo são normais: no registro de preços o órgão empenha
    em partes, quando precisa, enquanto a ata vale. `item` nulo = vale para a
    compra inteira (um contrato que cobre todos os itens ganhos).
    """

    class Tipo(models.TextChoices):
        CONTRATO = "contrato", "Contrato"
        ATA = "ata", "Ata de registro de preços"
        EMPENHO = "empenho", "Empenho"
        ORDEM_FORNECIMENTO = "ordem_fornecimento", "Ordem de fornecimento"
        LIQUIDACAO = "liquidacao", "Liquidação"
        PAGAMENTO = "pagamento", "Pagamento"

    oportunidade = models.ForeignKey(
        OportunidadeSalva,
        verbose_name="oportunidade",
        related_name="documentos_financeiros",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        help_text="Nulo = veio de um sistema e ainda não foi ligado a uma licitação.",
    )
    item = models.ForeignKey(
        ItemParticipado,
        verbose_name="item",
        related_name="documentos_financeiros",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    tipo = models.CharField("tipo", max_length=24, choices=Tipo.choices)
    numero = models.CharField("número", max_length=60, blank=True, help_text="Ex.: 2026NE000632.")
    data = models.DateField("data", null=True, blank=True)
    valor = models.DecimalField("valor", max_digits=18, decimal_places=2, null=True, blank=True)
    vigente_ate = models.DateField("vigente até", null=True, blank=True, help_text="Contrato e ata.")
    fonte = models.CharField("fonte", max_length=16, choices=Fonte.choices, default=Fonte.MANUAL)
    dados = models.JSONField("dados da fonte", default=dict, blank=True)
    criado_em = models.DateTimeField("lido em", auto_now_add=True)

    class Meta:
        verbose_name = "documento financeiro"
        verbose_name_plural = "documentos financeiros"
        ordering = ["data", "id"]
        constraints = [
            # A mesma nota de empenho lida duas vezes do Portal não duplica.
            models.UniqueConstraint(
                fields=["fonte", "tipo", "numero"],
                condition=~Q(numero=""),
                name="documento_financeiro_unico_por_fonte",
            )
        ]

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} {self.numero}".strip()


class Entrega(models.Model):
    """Uma entrega feita ao órgão. Lançada à mão: nenhum sistema público
    diz quando o caminhão chegou."""

    oportunidade = models.ForeignKey(
        OportunidadeSalva,
        verbose_name="oportunidade",
        related_name="entregas",
        on_delete=models.CASCADE,
    )
    item = models.ForeignKey(
        ItemParticipado,
        verbose_name="item",
        related_name="entregas",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    data = models.DateField("entregue em")
    nota_fiscal = models.CharField("nota fiscal", max_length=60, blank=True)
    observacao = models.TextField("observação", blank=True)
    criada_em = models.DateTimeField("lançada em", auto_now_add=True)

    class Meta:
        verbose_name = "entrega"
        verbose_name_plural = "entregas"
        ordering = ["data", "id"]

    def __str__(self) -> str:
        return f"Entrega de {self.data:%d/%m/%Y}"
