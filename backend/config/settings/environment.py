"""
Classe de infraestrutura que centraliza a leitura de variáveis de ambiente —
preenchidas via ConfigMap/Secret no Kubernetes (ver docs/ARQUITETURA.md,
seção "Configuração e segredos", no repositório principal).

Nenhum outro módulo do projeto chama `os.environ` diretamente: qualquer
componente que precise de uma configuração instancia `Environment()` (ou usa
o singleton `env` já pronto abaixo) e lê uma propriedade tipada — nunca uma
string solta de nome de variável espalhada pelo código.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _get_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    return int(value)


def _get_list(name: str, default: list[str]) -> list[str]:
    value = os.environ.get(name)
    if value is None:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Environment:
    """
    Uma instância = uma leitura consistente do ambiente no momento em que foi
    criada. Cada propriedade tem um default seguro para desenvolvimento local
    sem `.env` nenhum — em produção, o ConfigMap/Secret do Kubernetes
    preenche todas.
    """

    # Django
    debug: bool = field(default_factory=lambda: _get_bool("DJANGO_DEBUG", default=False))
    secret_key: str = field(
        default_factory=lambda: os.environ.get(
            "DJANGO_SECRET_KEY", "django-insecure-troque-esta-chave-em-producao"
        )
    )
    allowed_hosts: list[str] = field(
        default_factory=lambda: _get_list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
    )

    # PostgreSQL (ver docs/ARQUITETURA.md — StatefulSet + PVC dedicados)
    database_name: str = field(default_factory=lambda: os.environ.get("POSTGRES_DB", "licita"))
    database_user: str = field(default_factory=lambda: os.environ.get("POSTGRES_USER", "licita"))
    database_password: str = field(default_factory=lambda: os.environ.get("POSTGRES_PASSWORD", "licita"))
    database_host: str = field(default_factory=lambda: os.environ.get("POSTGRES_HOST", "localhost"))
    database_port: int = field(default_factory=lambda: _get_int("POSTGRES_PORT", default=5432))

    # RabbitMQ / Celery (ver docs/ARQUITETURA.md — Celery + RabbitMQ)
    rabbitmq_url: str = field(
        default_factory=lambda: os.environ.get("RABBITMQ_URL", "amqp://guest:guest@localhost:5672//")
    )

    # Integrações externas (ver apps/integracoes e docs/DOMINIO.md).
    compras_gov_base_url: str = field(
        default_factory=lambda: os.environ.get(
            "COMPRAS_GOV_BASE_URL", "https://dadosabertos.compras.gov.br"
        )
    )
    pncp_base_url: str = field(
        default_factory=lambda: os.environ.get("PNCP_BASE_URL", "https://pncp.gov.br")
    )
    # Portal da Transparência (CGU): empenho, liquidação e pagamento dos
    # órgãos federais. A chave é pessoal e gratuita (cadastro com gov.br em
    # portaldatransparencia.gov.br/api-de-dados/cadastrar-email) e vai no
    # cabeçalho `chave-api-dados`. Sem ela, a sincronia avisa e não roda.
    portal_transparencia_chave: str = field(
        default_factory=lambda: os.environ.get("PORTAL_TRANSPARENCIA_CHAVE", "")
    )
    portal_transparencia_base_url: str = field(
        default_factory=lambda: os.environ.get(
            "PORTAL_TRANSPARENCIA_BASE_URL", "https://api.portaldatransparencia.gov.br/api-de-dados"
        )
    )
    # Endpoint não documentado (ver docs/DOMINIO.md) — permite desligar em
    # produção se ele mudar/sumir sem aviso, caindo direto no catálogo local.
    usar_busca_pncp: bool = field(default_factory=lambda: _get_bool("USAR_BUSCA_PNCP", default=True))
    # Intervalo entre páginas no sync do catálogo de PDM — de propósito maior
    # que zero, para não gerar rajada de requisições numa API pública do
    # governo (ver docs/DOMINIO.md, seção "Integrações externas").
    catalogo_sync_intervalo_segundos: float = field(
        default_factory=lambda: float(os.environ.get("CATALOGO_SYNC_INTERVALO_SEGUNDOS", "0.3"))
    )

    # Armazenamento de arquivos (ver apps/armazenamento). Só a **chave de
    # cifra** vem do ambiente: o resto da configuração (driver, bucket,
    # credencial) é registro de banco, porque precisa ser por cliente e
    # mudável pela tela sem redeploy.
    #
    # Em branco, `apps/armazenamento/cripto.py` deriva uma chave da
    # SECRET_KEY — serve para desenvolvimento, mas em produção configure
    # esta: sem ela, rotacionar a SECRET_KEY torna ilegíveis as credenciais
    # já gravadas. Gerar com:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    armazenamento_chave_cifra: str = field(
        default_factory=lambda: os.environ.get("ARMAZENAMENTO_CHAVE_CIFRA", "")
    )

    # JWT (ver docs/ARQUITETURA.md — seção "Autenticação")
    jwt_access_lifetime_minutes: int = field(
        default_factory=lambda: _get_int("JWT_ACCESS_LIFETIME_MINUTES", default=15)
    )
    jwt_refresh_lifetime_days: int = field(
        default_factory=lambda: _get_int("JWT_REFRESH_LIFETIME_DAYS", default=30)
    )

    @property
    def database_options(self) -> dict[str, str | int]:
        """Pronto para `DATABASES["default"]` em `settings/base.py`."""
        return {
            "NAME": self.database_name,
            "USER": self.database_user,
            "PASSWORD": self.database_password,
            "HOST": self.database_host,
            "PORT": self.database_port,
        }


# Singleton de conveniência — a maioria do código só precisa disso.
# `Environment()` continua disponível para quem preferir instanciar o
# próprio (ex.: um teste que quer isolar variáveis de ambiente específicas).
env = Environment()
