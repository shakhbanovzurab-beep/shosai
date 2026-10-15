#!/bin/sh
# Сертификат Let's Encrypt для edge staging (F4-D7). Запуск от root на сервере staging:
#   sh certificate.sh issue /srv/shosai   — первый выпуск: certbot сам слушает порт 80 (edge ещё нет);
#   sh certificate.sh renew /srv/shosai   — продление через webroot работающего edge (таймер systemd).
# После выпуска или продления цепочка и ключ копируются в tls/edge для NGINX (uid 101), и edge
# перечитывает конфигурацию. Адрес почты Let's Encrypt не передаётся: уведомлений он больше не шлёт.
set -eu
action="${1:?issue или renew}"
target="${2:?каталог staging, например /srv/shosai}"
domain="${SHOSAI_SERVER_NAME:-shosai.tech}"
certbot_image="certbot/certbot:v5.8.0"
install -d -m 755 "$target/acme" "$target/letsencrypt"
install -d -m 750 -o 101 -g 101 "$target/tls/edge"
case "$action" in
  issue)
    docker run --rm -p 80:80 -v "$target/letsencrypt:/etc/letsencrypt" "$certbot_image" \
      certonly --standalone --non-interactive --agree-tos --register-unsafely-without-email \
      --key-type ecdsa -d "$domain"
    ;;
  renew)
    docker run --rm -v "$target/letsencrypt:/etc/letsencrypt" -v "$target/acme:/var/www/acme" \
      "$certbot_image" renew --non-interactive --webroot -w /var/www/acme
    ;;
  *)
    echo "certificate.sh: неизвестное действие $action" >&2
    exit 2
    ;;
esac
live="$target/letsencrypt/live/$domain"
install -m 644 -o 101 -g 101 "$live/fullchain.pem" "$target/tls/edge/fullchain.pem"
install -m 600 -o 101 -g 101 "$live/privkey.pem" "$target/tls/edge/privkey.pem"
if [ "$action" = renew ]; then
  docker compose --project-directory "$target" exec -T edge nginx -s reload
fi
