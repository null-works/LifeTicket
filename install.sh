#!/usr/bin/env bash
set -euo pipefail

DOMAIN="calendar.kylem.cc"
APP_PORT=5050

echo "=== LifeTicket Installer ==="

# --- Pre-flight checks ---
if [ "$EUID" -ne 0 ]; then
  echo "Error: Please run as root (sudo ./install.sh)"
  exit 1
fi

command -v docker >/dev/null 2>&1 || { echo "Error: docker is not installed"; exit 1; }
command -v docker compose >/dev/null 2>&1 || docker compose version >/dev/null 2>&1 || { echo "Error: docker compose is not available"; exit 1; }

# --- Generate .env if missing ---
if [ ! -f .env ]; then
  SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")

  read -rp "Admin username [admin]: " ADMIN_USER
  ADMIN_USER="${ADMIN_USER:-admin}"

  while true; do
    read -rsp "Admin password: " ADMIN_PASS
    echo
    if [ -z "$ADMIN_PASS" ]; then
      echo "Password cannot be empty. Try again."
    else
      break
    fi
  done

  cat > .env <<ENVFILE
SECRET_KEY=${SECRET}
ADMIN_USERNAME=${ADMIN_USER}
ADMIN_PASSWORD=${ADMIN_PASS}
ENVFILE
  chmod 600 .env
  echo "Generated .env with SECRET_KEY and admin credentials"
else
  echo ".env already exists, skipping"
  if ! grep -q ADMIN_PASSWORD .env; then
    echo "WARNING: .env is missing ADMIN_PASSWORD — add it before deploying"
  fi
fi

# --- Build and start the app ---
echo "Building and starting LifeTicket..."
docker compose up -d --build

# --- Install Nginx + Certbot if needed ---
if ! command -v nginx >/dev/null 2>&1; then
  echo "Installing nginx..."
  apt-get update -qq && apt-get install -y -qq nginx
fi

if ! command -v certbot >/dev/null 2>&1; then
  echo "Installing certbot..."
  apt-get update -qq && apt-get install -y -qq certbot python3-certbot-nginx
fi

# --- Configure Nginx ---
NGINX_CONF="/etc/nginx/sites-available/${DOMAIN}"

cat > "$NGINX_CONF" <<NGINX
server {
    listen 80;
    server_name ${DOMAIN};

    location / {
        proxy_pass http://127.0.0.1:${APP_PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
NGINX

ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
echo "Nginx configured for ${DOMAIN}"

# --- SSL via Certbot ---
echo "Obtaining SSL certificate..."
certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --redirect \
  --register-unsafely-without-email || {
    echo ""
    echo "Certbot failed. Make sure DNS for ${DOMAIN} points to this server."
    echo "You can retry manually: sudo certbot --nginx -d ${DOMAIN}"
    exit 1
  }

echo ""
echo "=== Done! ==="
echo "LifeTicket is live at https://${DOMAIN}"
