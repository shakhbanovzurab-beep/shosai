#!/bin/sh
# Самоподписанный сертификат локального edge (deploy/local/compose.app.yaml): edge без TLS не
# стартует, а локально Let's Encrypt не выдаёт. Пишет deploy/local/tls/edge.{crt,key}; каталог в
# .gitignore. Повторный запуск ничего не делает, пока сертификату больше 30 дней.
set -eu

dir="$(dirname "$0")/tls"
mkdir -p "$dir"

if [ -f "$dir/edge.crt" ] && openssl x509 -checkend 2592000 -noout -in "$dir/edge.crt" >/dev/null; then
  exit 0
fi

openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:P-256 -nodes -days 365 \
  -subj "/CN=edge" -addext "subjectAltName=DNS:edge,DNS:localhost,IP:127.0.0.1" \
  -keyout "$dir/edge.key" -out "$dir/edge.crt" 2>/dev/null
# Ключ читает nginx edge (uid 101); сертификат только локальный и самоподписанный.
chmod 644 "$dir/edge.key" "$dir/edge.crt"
echo "сертификат локального edge: $dir/edge.crt"
