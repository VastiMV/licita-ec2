from django.urls import path

from .views import (
    CicloView,
    CompraDetalheView,
    EmCotacaoView,
    DescartadasView,
    EncerradasView,
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
]
