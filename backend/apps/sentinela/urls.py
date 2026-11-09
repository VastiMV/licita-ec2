from django.urls import path

from .views import CamadaView, CapturaView, EstadoView, PulsoView, RondaView

urlpatterns = [
    path("pulso/", PulsoView.as_view(), name="sentinela-pulso"),
    path("captura/", CapturaView.as_view(), name="sentinela-captura"),
    path("camada/<str:codigo>/", CamadaView.as_view(), name="sentinela-camada"),
    path("ronda/", RondaView.as_view(), name="sentinela-ronda"),
    path("estado/", EstadoView.as_view(), name="sentinela-estado"),
]
