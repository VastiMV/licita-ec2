#!/usr/bin/env bash
# Baixa as imagens mais novas do GitHub e reinicia o que mudou. É o que o
# botão "Deploy EC2" do GitHub roda; também dá para rodar à mão no EC2:
#   sudo /opt/licita/atualizar.sh
set -euo pipefail
cd "$(dirname "$0")"

# Backup do banco ANTES de qualquer coisa: o `up` abaixo roda as migrações,
# e uma migração que estraga dados não tem volta sem ele. Se o backup falhar,
# o deploy para aqui e a produção continua como estava.
BACKUPS="$(pwd)/backups"
MANTER=10
mkdir -p "$BACKUPS"
if docker compose ps --status running --services 2>/dev/null | grep -qx postgres; then
  arquivo="$BACKUPS/licita-$(date +%Y%m%d-%H%M%S).dump"
  # Nunca sobrescreve um backup que já existe (dois deploys no mesmo segundo).
  [ -e "$arquivo" ] && arquivo="${arquivo%.dump}-$$.dump"
  docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$arquivo"
  if [ ! -s "$arquivo" ]; then
    rm -f "$arquivo"
    echo "Backup do banco saiu vazio. Deploy cancelado; nada foi alterado." >&2
    exit 1
  fi
  echo "Backup do banco: $arquivo ($(du -h "$arquivo" | cut -f1))"
  # Guarda só os mais recentes, para não encher o disco.
  ls -1t "$BACKUPS"/licita-*.dump | tail -n +$((MANTER + 1)) | xargs -r rm --
else
  echo "Postgres não está rodando: sem backup (primeira instalação?)."
fi

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
