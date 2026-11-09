import re
import time

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import User


class LoginSerializer(TokenObtainPairSerializer):
    """
    `TokenObtainPairSerializer` puro só carrega `user_id` no payload do
    `access` — embarcamos `email`/`nome` também, para o menu de perfil do
    Angular (`AuthService.usuario`) exibi-los sem precisar de outro
    endpoint.
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["email"] = user.email
        token["nome"] = user.nome
        # Configurações (armazenamento e usuários) é só do super usuário
        # (ver `permissions.EhSuperusuario`). Sem esta claim, o menu teria
        # que mostrar o item a todo mundo e deixar o 403 explicar — a
        # permissão continua sendo do backend, isto é só para não oferecer o
        # que a pessoa não pode usar.
        token["is_superuser"] = user.is_superuser
        # A hora da entrada: a renovação copia a claim para o refresh novo, e
        # `RefreshView` recusa depois de `sessao_maxima_horas` (12h).
        token["login_em"] = int(time.time())
        return token


class UsuarioSerializer(serializers.ModelSerializer):
    """O cadastro da tela de Usuários: nome, e-mail, super usuário ou não, e
    a senha.

    A senha só entra: nunca sai na resposta. Obrigatória ao cadastrar; ao
    editar, em branco quer dizer "manter a atual".
    """

    senha = serializers.CharField(
        write_only=True, required=False, allow_blank=True, trim_whitespace=False
    )

    class Meta:
        model = User
        fields = ["id", "nome", "email", "is_superuser", "senha", "criado_em"]
        read_only_fields = ["id", "criado_em"]
        extra_kwargs = {
            # "Nome visual" é o que aparece no histórico de tudo que a pessoa
            # fizer — sem ele o registro mostraria o e-mail.
            "nome": {"required": True, "allow_blank": False},
            # A unicidade é conferida em `validate_email`, sem diferenciar
            # maiúscula — o validador padrão diferenciaria.
            "email": {"validators": []},
        }

    def validate_email(self, email: str) -> str:
        email = User.objects.normalize_email(email).strip()
        existentes = User.objects.filter(email__iexact=email)
        if self.instance:
            existentes = existentes.exclude(pk=self.instance.pk)
        if existentes.exists():
            raise serializers.ValidationError("Já existe um usuário com este e-mail.")
        return email

    def validate_is_superuser(self, valor: bool) -> bool:
        # Tirar de si mesmo o super usuário pode deixar o produto sem
        # ninguém que consiga devolvê-lo — outro super usuário é quem faz.
        eu = self.context.get("request").user if self.context.get("request") else None
        if self.instance and eu and self.instance.pk == eu.pk and not valor:
            raise serializers.ValidationError(
                "Você não pode tirar de si mesmo o super usuário."
            )
        return valor

    def validate(self, dados: dict) -> dict:
        senha = dados.get("senha") or ""
        if not self.instance and not senha:
            raise serializers.ValidationError({"senha": "Informe a senha."})
        if senha:
            try:
                validate_password(senha, user=self.instance)
            except DjangoValidationError as erro:
                raise serializers.ValidationError({"senha": list(erro.messages)}) from erro
        return dados

    def save(self, **kwargs) -> User:
        senha = self.validated_data.pop("senha", "")
        # O admin do Django acompanha o super usuário: não há um segundo
        # recorte de acesso para a equipe administrar.
        if "is_superuser" in self.validated_data:
            self.validated_data["is_staff"] = self.validated_data["is_superuser"]
        usuario = super().save(**kwargs)
        if senha:
            usuario.set_password(senha)
            usuario.save(update_fields=["password"])
        return usuario


class PerfilSerializer(UsuarioSerializer):
    """O próprio usuário editando o perfil: o mesmo cadastro, mas o super
    usuário não é dele para mudar — só aparece. A foto vem junto (só aqui, não
    na lista de usuários) e muda por `PUT/DELETE /api/usuarios/eu/foto/`."""

    class Meta(UsuarioSerializer.Meta):
        fields = UsuarioSerializer.Meta.fields + ["foto"]
        read_only_fields = ["id", "criado_em", "is_superuser", "foto"]


FOTO_FORMATO = re.compile(r"^data:image/(png|jpeg|webp);base64,[A-Za-z0-9+/=]+$")
FOTO_TAMANHO_MAXIMO = 400_000  # caracteres (~300 KB); a tela manda ~30 KB


class FotoSerializer(serializers.Serializer):
    foto = serializers.CharField(max_length=FOTO_TAMANHO_MAXIMO, trim_whitespace=True)

    def validate_foto(self, foto: str) -> str:
        if not FOTO_FORMATO.match(foto):
            raise serializers.ValidationError("Envie uma imagem PNG, JPEG ou WEBP.")
        return foto
