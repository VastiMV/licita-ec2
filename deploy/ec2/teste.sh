#!/usr/bin/env bash
# Liga e desliga o AMBIENTE DE TESTE. É o que os botões "Teste: ligar" e
# "Teste: desligar" do GitHub rodam no EC2:
#
#   sudo /opt/licita-teste/teste.sh ligar
#   sudo /opt/licita-teste/teste.sh desligar
#   sudo /opt/licita-teste/teste.sh desligar --apagar-dados
#
# Nunca toca na produção (/opt/licita): pasta, banco e senhas são outros.
set -euo pipefail
cd "$(dirname "$0")"

PRODUCAO=/opt/licita

case "${1:-}" in
  ligar)
    if [ ! -f "$PRODUCAO/.env" ]; then
      echo "A produção ainda não foi instalada ($PRODUCAO/.env não existe)." >&2
      exit 1
    fi

    # Senhas próprias do teste, geradas na primeira vez. O endereço é o da
    # produção com "teste." na frente.
    if [ ! -f .env ]; then
      DOMINIO=$(grep '^DOMINIO=' "$PRODUCAO/.env" | cut -d= -f2-)
      RMQ=$(openssl rand -hex 24)
      cat > .env <<ENV
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=$(openssl rand -hex 50)
DJANGO_ALLOWED_HOSTS=teste.$DOMINIO,teste.insidelicitacoes.com.br
ARMAZENAMENTO_CHAVE_CIFRA=$(openssl rand -base64 32 | tr '+/' '-_')

POSTGRES_DB=licita
POSTGRES_USER=licita
POSTGRES_PASSWORD=$(openssl rand -hex 24)
POSTGRES_HOST=teste-postgres
POSTGRES_PORT=5432

RABBITMQ_DEFAULT_USER=licita
RABBITMQ_DEFAULT_PASS=$RMQ
RABBITMQ_URL=amqp://licita:$RMQ@teste-rabbitmq:5672//
ENV
      chmod 600 .env
      echo "Senhas do teste criadas em $(pwd)/.env"
    fi

    docker compose -f docker-compose.teste.yml pull --quiet
    docker compose -f docker-compose.teste.yml up -d --remove-orphans
    docker image prune -f >/dev/null

    DOMINIO=$(grep '^DOMINIO=' "$PRODUCAO/.env" | cut -d= -f2-)
    echo
    echo "Teste ligado: https://teste.$DOMINIO"
    docker compose -f docker-compose.teste.yml ps --format 'table {{.Service}}\t{{.Status}}'
    ;;

  desligar)
    if [ "${2:-}" = "--apagar-dados" ]; then
      docker compose -f docker-compose.teste.yml down --volumes
      echo "Teste desligado e dados do teste APAGADOS (a produção não foi tocada)."
    else
      docker compose -f docker-compose.teste.yml down
      echo "Teste desligado. Os dados do teste ficam guardados para a próxima vez."
    fi
    ;;

  *)
    echo "Uso: teste.sh ligar | desligar [--apagar-dados]" >&2
    exit 1
    ;;
esac
