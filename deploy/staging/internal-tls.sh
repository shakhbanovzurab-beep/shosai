#!/bin/sh
# Внутренний TLS staging (F4 шаг 3): свой CA и сертификат PgBouncer обоих домов.
# Приложение ходит в PgBouncer с sslmode=verify-full (гейт, core/config/gate.py), поэтому
# сертификат PgBouncer подписан этим CA и называет оба имени сервиса: pgbouncer-ru, pgbouncer-eu.
# Запуск от root на сервере staging: sh deploy/staging/internal-tls.sh /srv/shosai
# Повторный запуск ничего не меняет, пока сертификат действителен дольше 30 дней.
set -eu
target="${1:?каталог staging, например /srv/shosai}"
repository="$(cd "$(dirname "$0")" && pwd)"
ca_dir="$target/tls/ca"
shared="$target/tls/shared"
install -d -m 700 -o root -g root "$ca_dir"
install -d -m 755 -o root -g root "$shared"
umask 077
if [ ! -f "$ca_dir/internal-ca.key" ]; then
  openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:P-256 -nodes -days 3650 \
    -subj "/O=Shosai staging/CN=Shosai staging internal CA" \
    -keyout "$ca_dir/internal-ca.key" -out "$ca_dir/internal-ca.crt" 2>/dev/null
fi
if [ ! -f "$shared/pgbouncer.crt" ] || ! openssl x509 -checkend 2592000 -noout -in "$shared/pgbouncer.crt" >/dev/null; then
  openssl req -newkey ec -pkeyopt ec_paramgen_curve:P-256 -nodes \
    -subj "/O=Shosai staging/CN=pgbouncer" \
    -keyout "$ca_dir/pgbouncer.key" -out "$ca_dir/pgbouncer.csr" 2>/dev/null
  printf 'subjectAltName=DNS:pgbouncer-ru,DNS:pgbouncer-eu\nextendedKeyUsage=serverAuth\n' > "$ca_dir/pgbouncer.ext"
  openssl x509 -req -in "$ca_dir/pgbouncer.csr" -CA "$ca_dir/internal-ca.crt" -CAkey "$ca_dir/internal-ca.key" \
    -CAcreateserial -days 825 -extfile "$ca_dir/pgbouncer.ext" -out "$ca_dir/pgbouncer.crt" 2>/dev/null
  install -m 644 -o root -g root "$ca_dir/pgbouncer.crt" "$shared/pgbouncer.crt"
  # Ключ читает только процесс PgBouncer (uid 70 в его образе).
  install -m 600 -o 70 -g 70 "$ca_dir/pgbouncer.key" "$shared/pgbouncer.key"
fi
install -m 644 -o root -g root "$ca_dir/internal-ca.crt" "$shared/internal-ca.crt"
install -m 644 -o root -g root "$repository/tls/timeweb-ca.crt" "$shared/timeweb-ca.crt"
