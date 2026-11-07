#!/usr/bin/env bash
# Baixa as imagens mais novas do GitHub e reinicia o que mudou. É o que o
# botão "Deploy EC2" do GitHub roda; também dá para rodar à mão no EC2:
#   sudo /opt/licita/atualizar.sh
set -euo pipefail
cd "$(dirname "$0")"

docker compose pull --quiet
# `up` roda a migração antes de subir o backend (ver docker-compose.yml).
docker compose up -d --remove-orphans
# O Caddyfile é um arquivo montado: mudar ele não recria o container, então
# a configuração nova (ex.: o endereço do teste) entra por reload.
docker compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile \
  || docker compose restart caddy
docker image prune -f >/dev/null

echo "Licita atualizado:"
docker compose ps --format 'table {{.Service}}\t{{.Status}}'
