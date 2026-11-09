"""
Settings do projeto Licita.

Nenhuma configuração lê `os.environ` diretamente aqui — tudo vem de
`environment.env` (ver `environment.py`), a classe de infraestrutura que
concentra a leitura de variáveis de ambiente (preenchidas via ConfigMap/
Secret no Kubernetes). Ver docs/ARQUITETURA.md no repositório principal.
"""

from datetime import timedelta
from pathlib import Path

from .environment import env

# backend/config/settings/base.py -> backend/
BASE_DIR = Path(__file__).resolve().parent.parent.parent


SECRET_KEY = env.secret_key
DEBUG = env.debug
ALLOWED_HOSTS = env.allowed_hosts


# Application definition

INSTALLED_APPS = [
    # 'daphne' primeiro: é o que faz `manage.py runserver` servir via ASGI
    # (Daphne) em vez do WSGI de desenvolvimento padrão — necessário para
    # qualquer `async def` view e para o roteamento de websocket do Channels.
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Extensão Postgres — GinIndex/TrigramSimilarity da busca do catálogo
    # (ver apps/catalogo/models.py e apps/catalogo/search.py).
    "django.contrib.postgres",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "channels",
    "django_celery_beat",
    "apps.accounts",
    "apps.tenants",
    "apps.armazenamento",
    "apps.integracoes",
    "apps.catalogo",
    "apps.capag",
    "apps.licitacoes",
    "apps.empresas",
    "apps.documentos",
    "apps.fornecedores",
    "apps.produtos",
    "apps.cotador",
    "apps.propostas",
    "apps.sentinela",
    "apps.notificacoes",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        **env.database_options,
    }
}


# Usuário — model próprio desde o primeiro migrate (trocar depois é doloroso).
# Ver apps/accounts/models.py e docs/DOMINIO.md.
AUTH_USER_MODEL = "accounts.User"


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = "static/"

# Onde o driver `local` de `apps/armazenamento` grava. Só desenvolvimento e
# testes: o pod é efêmero e não compartilha disco (ver docs/ARQUITETURA.md,
# "Pods"), então em produção o driver é o de bucket. Nada é servido
# diretamente daqui — o download passa por link assinado
# (`DownloadLocalView`), como no bucket.
MEDIA_ROOT = BASE_DIR / "arquivos"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Django REST Framework — API JWT-only, sem sessão para os clients (ver
# docs/ARQUITETURA.md, seção "Autenticação"). Sessão do Django continua
# existindo só para o /admin/.

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        # Antes do JWT: a chave de leitura (só GET) — ver apps/accounts/leitura.py.
        "apps.accounts.leitura.ChaveDeLeitura",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env.jwt_access_lifetime_minutes),
    # O login vale no máximo `sessao_maxima_horas` desde a entrada (claim
    # `login_em`, conferida em `RefreshView`); o refresh nunca dura mais que isso.
    "REFRESH_TOKEN_LIFETIME": min(
        timedelta(days=env.jwt_refresh_lifetime_days), timedelta(hours=env.sessao_maxima_horas)
    ),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
}

# Cookie do CSRF (usado só por /api/auth/refresh/ — ver apps/accounts/views.py)
# e cookie de sessão (usado só pelo /admin/): `Secure` em produção, liberado
# em DEBUG porque o dev local roda em http:// puro.
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG

# O Ingress (Traefik, ver k8s/ingress.yaml) termina o TLS e repassa pro
# backend em HTTP puro — sem isto, `request.is_secure()` dá False mesmo em
# produção, o Django monta a origem esperada como "http://<host>" e rejeita
# todo POST vindo do navegador em "https://<host>" com "Origin checking
# failed" (403). Era isso que derrubava a sessão a cada 15 min: todo
# refresh de token batia em /api/auth/refresh/, que exige CSRF de verdade
# (ver apps/accounts/views.py), e caía nesse 403 sempre — nunca era o
# refresh token em si que expirava.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


# Celery + RabbitMQ — ver docs/ARQUITETURA.md, seção "Assíncrono".
# Nenhuma task ainda: só o app Celery instanciado (config/celery.py) e o
# agendador do django-celery-beat, prontos para quando `catalogo`/`alertas`
# existirem.

CELERY_BROKER_URL = env.rabbitmq_url
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"


# Channels — sem consumidor de websocket ainda (ver config/asgi.py); a
# camada em memória serve para desenvolvimento local e para os testes. Uma
# camada real (Redis) entra quando o primeiro consumer existir.
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}
