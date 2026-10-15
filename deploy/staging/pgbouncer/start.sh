#!/bin/sh
# Старт PgBouncer дома на staging: список пользователей и адрес кластера — из окружения,
# в tmpfs /run/pgbouncer; сам конфиг — только для чтения.
set -eu
: "${PGBOUNCER_APP_USER:?PGBOUNCER_APP_USER не задан}"
: "${PGBOUNCER_APP_PASSWORD:?PGBOUNCER_APP_PASSWORD не задан}"
: "${PGBOUNCER_SERVER_HOST:?PGBOUNCER_SERVER_HOST не задан}"
: "${PGBOUNCER_SERVER_DATABASE:?PGBOUNCER_SERVER_DATABASE не задан}"
case "${PGBOUNCER_APP_USER}${PGBOUNCER_APP_PASSWORD}" in
  *'"'*)
    echo "pgbouncer: имя или пароль роли приложения содержит двойную кавычку" >&2
    exit 1
    ;;
esac
umask 077
printf '"%s" "%s"\n' "${PGBOUNCER_APP_USER}" "${PGBOUNCER_APP_PASSWORD}" \
  > /run/pgbouncer/userlist.txt
# Только база дома: другие имена PgBouncer не обслуживает.
printf '[databases]\n%s = host=%s port=5432 dbname=%s\n' \
  "${PGBOUNCER_SERVER_DATABASE}" "${PGBOUNCER_SERVER_HOST}" "${PGBOUNCER_SERVER_DATABASE}" \
  > /run/pgbouncer/databases.ini
exec pgbouncer /etc/pgbouncer/pgbouncer.ini
