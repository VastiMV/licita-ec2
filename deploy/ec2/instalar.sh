#!/usr/bin/env bash
# Instala o Licita num EC2 Ubuntu novo. Rode UMA vez, como o usuário ubuntu:
#
#   curl -fsSL https://raw.githubusercontent.com/VastiMV/licita-ec2/main/deploy/ec2/instalar.sh | bash -s -- insidelicitacoes.com.br
#
# Faz: swap, Docker, a pasta /opt/licita com os arquivos do deploy e o .env
# com senhas aleatórias. Quem sobe o sistema é o botão "Deploy EC2" do
# GitHub (ele faz o login no registro de imagens). Rodar de novo é seguro:
# não troca as senhas de um .env que já existe.
#
# LICITA_RAW troca de onde os arquivos são baixados (útil para testar uma
# branch antes do merge).
set -euo pipefail

DOMINIO="${1:-}"
if [ -z "$DOMINIO" ]; then
  echo "Uso: bash instalar.sh seu-dominio.com.br" >&2
  exit 1
fi
PASTA="${LICITA_PASTA:-/opt/licita}"
RAW="${LICITA_RAW:-https://raw.githubusercontent.com/VastiMV/licita-ec2/main/deploy/ec2}"

echo "==> 1/4 Memória extra (swap de 2 GB)"
if [ "${LICITA_SEM_SWAP:-}" != "1" ] && ! swapon --show | grep -q /swapfile; then
  sudo fallocate -l 2G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile >/dev/null
  sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi

echo "==> 2/4 Docker"
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
fi

echo "==> 3/4 Arquivos em $PASTA"
sudo mkdir -p "$PASTA"
sudo chown "$(id -u)":"$(id -g)" "$PASTA"
for arquivo in docker-compose.yml Caddyfile atualizar.sh; do
  curl -fsSL "$RAW/$arquivo" -o "$PASTA/$arquivo"
done
mkdir -p "$PASTA/.well-known"
curl -fsSL "$RAW/.well-known/security.txt" -o "$PASTA/.well-known/security.txt"
chmod +x "$PASTA/atualizar.sh"

echo "==> 4/4 Senhas (.env)"
if [ ! -f "$PASTA/.env" ]; then
  PG=$(openssl rand -hex 24)
  RMQ=$(openssl rand -hex 24)
  cat > "$PASTA/.env" <<ENV
DOMINIO=$DOMINIO
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=$(openssl rand -hex 50)
DJANGO_ALLOWED_HOSTS=$DOMINIO,www.$DOMINIO
ARMAZENAMENTO_CHAVE_CIFRA=$(openssl rand -base64 32 | tr '+/' '-_')

POSTGRES_DB=licita
POSTGRES_USER=licita
POSTGRES_PASSWORD=$PG
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

RABBITMQ_DEFAULT_USER=licita
RABBITMQ_DEFAULT_PASS=$RMQ
RABBITMQ_URL=amqp://licita:$RMQ@rabbitmq:5672//
ENV
  chmod 600 "$PASTA/.env"
  echo "    .env criado. GUARDE UMA CÓPIA: sem ele, o banco não abre."
else
  echo "    .env já existe — mantido."
fi

cat <<FIM

Máquina pronta! Agora:

  1. No GitHub (VastiMV/licita-ec2) → Actions → "Deploy EC2" → Run workflow.
  2. Quando terminar, volte aqui e crie o seu login:

     cd $PASTA && sudo docker compose exec backend python manage.py createsuperuser

  3. Abra https://$DOMINIO
     (o cadeado aparece quando o DNS do domínio aponta para este servidor).
FIM
