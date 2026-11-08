from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models


class UserManager(BaseUserManager):
    """`create_user`/`create_superuser` por e-mail — não há `username`."""

    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra_fields) -> "User":
        if not email:
            raise ValueError("O e-mail é obrigatório.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra_fields) -> "User":
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email: str, password: str | None = None, **extra_fields) -> "User":
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superusuário precisa de is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superusuário precisa de is_superuser=True.")

        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Usuário autenticado da plataforma — dono de `Filtro` (ver
    docs/DOMINIO.md no repositório principal). Login é por e-mail, não por
    username: o protótipo original não tinha conceito de usuário nenhum, e
    o e-mail já era o dado que o `Filtro` guardava para notificação.
    """

    email = models.EmailField("e-mail", unique=True)
    nome = models.CharField("nome", max_length=150, blank=True)
    # A foto do círculo do topo (pedido da operação, 08/11/2026). Guardada como
    # `data:image/jpeg;base64,…`, já reduzida a 256×256 no navegador (~30 KB):
    # aparece sem depender do armazenamento de arquivos. Vazia = a inicial.
    foto = models.TextField("foto", blank=True)

    is_staff = models.BooleanField(
        "acesso ao admin",
        default=False,
        help_text="Permite entrar no /admin/ do Django.",
    )
    is_active = models.BooleanField(
        "ativo",
        default=True,
        help_text="Contas inativas não conseguem autenticar, sem precisar apagar o registro.",
    )
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        verbose_name = "usuário"
        verbose_name_plural = "usuários"
        ordering = ["email"]

    def __str__(self) -> str:
        return self.email
