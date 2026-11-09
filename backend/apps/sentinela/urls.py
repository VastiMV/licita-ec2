from django.urls import path

from .views import CamadaView, CapturaView, EstadoView, PulsoView, RondaView, TarefasView, TarefaView

urlpatterns = [
    path("pulso/", PulsoView.as_view(), name="sentinela-pulso"),
    path("captura/", CapturaView.as_view(), name="sentinela-captura"),
    path("camada/<str:codigo>/", CamadaView.as_view(), name="sentinela-camada"),
    path("ronda/", RondaView.as_view(), name="sentinela-ronda"),
    path("estado/", EstadoView.as_view(), name="sentinela-estado"),
    path("tarefas/", TarefasView.as_view(), name="sentinela-tarefas"),
    path("tarefas/<int:pk>/", TarefaView.as_view(), name="sentinela-tarefa"),
]
