#!/bin/bash
set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${DEPLOY_DIR}"

source .env 2>/dev/null || true

DOMAIN="${DOMAIN:?Set DOMAIN in .env}"
EMAIL="${CERTBOT_EMAIL:?Set CERTBOT_EMAIL in .env}"
CERT_DIR="./stacks/frontend/nginx/ssl"
LE_DIR="/etc/letsencrypt/live/${DOMAIN}"

echo "==> Initializing SSL for ${DOMAIN}"

# 1. Create self-signed cert so nginx can start
mkdir -p "${CERT_DIR}"

# Certbot stores certs in /etc/letsencrypt inside the container.
# For the initial bootstrap, we create a temporary self-signed cert
# in the letsencrypt volume path so nginx can start.
docker compose -f stacks/frontend/docker-compose.yml run --rm --entrypoint "" certbot sh -c "
  mkdir -p ${LE_DIR} &&
  openssl req -x509 -nodes -days 1 -newkey rsa:2048 \
    -keyout ${LE_DIR}/privkey.pem \
    -out ${LE_DIR}/fullchain.pem \
    -subj '/CN=${DOMAIN}'
"

# 2. Start nginx (reads self-signed cert from letsencrypt volume)
echo "==> Starting nginx with temporary certificate..."
docker compose -f stacks/frontend/docker-compose.yml up -d nginx

# Wait for nginx to be ready
sleep 3

# 3. Get real cert via ACME challenge
echo "==> Requesting certificate from Let's Encrypt..."
docker compose -f stacks/frontend/docker-compose.yml run --rm certbot \
  certonly --webroot -w /var/www/certbot \
  -d "${DOMAIN}" --email "${EMAIL}" \
  --agree-tos --no-eff-email --force-renewal

# 4. Reload nginx with real cert
echo "==> Reloading nginx with real certificate..."
docker compose -f stacks/frontend/docker-compose.yml exec nginx nginx -s reload

echo ""
echo "SSL certificate obtained for ${DOMAIN}"
echo "  Certbot renewal sidecar will auto-renew."
echo "  Start with: docker compose -f stacks/frontend/docker-compose.yml --profile ssl up -d"
