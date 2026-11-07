from django.urls import path

from .views import (
    CicloView,
    CompraDetalheView,
    DocumentoFinanceiroView,
    DocumentosFinanceirosView,
    EmCotacaoView,
    DescartadasView,
    EncerradasView,
    EntregasView,
    EntregaView,
    OportunidadeSalvaEventosView,
    OportunidadeSalvaView,
    OportunidadesSalvasChavesView,
    OportunidadesSalvasView,
    OportunidadesView,
    ProcessoView,
    TorreView,
)

urlpatterns = [
    path("oportunidades/", OportunidadesView.as_view(), name="licitacoes-oportunidades"),
    path("ciclo/", CicloView.as_view(), name="licitacoes-ciclo"),
    path("torre/", TorreView.as_view(), name="licitacoes-torre"),
    path("cotacoes/", EmCotacaoView.as_view(), name="licitacoes-cotacoes"),
    path("encerradas/", EncerradasView.as_view(), name="licitacoes-encerradas"),
    path("descartadas/", DescartadasView.as_view(), name="licitacoes-descartadas"),
    path(
        "compras/<str:cnpj>/<int:ano>/<int:sequencial>/detalhe/",
        CompraDetalheView.as_view(),
        name="licitacoes-compra-detalhe",
    ),
    # Salvas — as rotas de nome fixo vêm antes da de <int:pk> por clareza
    # (não conflitam: "chaves" não casa com <int:pk>).
    path("salvas/", OportunidadesSalvasView.as_view(), name="licitacoes-salvas"),
    path("salvas/chaves/", OportunidadesSalvasChavesView.as_view(), name="licitacoes-salvas-chaves"),
    path("salvas/<int:pk>/", OportunidadeSalvaView.as_view(), name="licitacoes-salva"),
    path(
        "salvas/<int:pk>/eventos/",
        OportunidadeSalvaEventosView.as_view(),
        name="licitacoes-salva-eventos",
    ),
    path("salvas/<int:pk>/processo/", ProcessoView.as_view(), name="licitacoes-salva-processo"),
    # Torre de Controle — lançamento manual do que nenhum sistema informa.
    path(
        "salvas/<int:pk>/documentos-financeiros/",
        DocumentosFinanceirosView.as_view(),
        name="licitacoes-salva-documentos-financeiros",
    ),
    path("salvas/<int:pk>/entregas/", EntregasView.as_view(), name="licitacoes-salva-entregas"),
    path(
        "documentos-financeiros/<int:pk>/",
        DocumentoFinanceiroView.as_view(),
        name="licitacoes-documento-financeiro",
    ),
    path("entregas/<int:pk>/", EntregaView.as_view(), name="licitacoes-entrega"),
]
