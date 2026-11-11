from django.urls import path

from .views import LoginView, LogoutView, PasseDocumentacaoView, RefreshView, VerificarDocumentacaoView

urlpatterns = [
    path("login/", LoginView.as_view(), name="auth-login"),
    path("refresh/", RefreshView.as_view(), name="auth-refresh"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("documentacao/", PasseDocumentacaoView.as_view(), name="auth-documentacao"),
    path("documentacao/verificar/", VerificarDocumentacaoView.as_view(), name="auth-documentacao-verificar"),
]
