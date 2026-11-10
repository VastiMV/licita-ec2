from django.urls import path

from .views import LidasView, NotificacoesView, TesteTelegramView

urlpatterns = [
    path("", NotificacoesView.as_view(), name="notificacoes"),
    path("lidas/", LidasView.as_view(), name="notificacoes-lidas"),
    path("teste-telegram/", TesteTelegramView.as_view(), name="notificacoes-teste-telegram"),
]
