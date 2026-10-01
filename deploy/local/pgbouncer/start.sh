#!/bin/sh
# Запуск локального PgBouncer: файл пользователей собирается из переменных
# окружения в tmpfs, чтобы пароль не лежал ни в git, ни в образе.
# Через PgBouncer ходит только роль приложения; роль миграций подключается к
# PostgreSQL напрямую.
set -eu

: "${PGBOUNCER_APP_USER:?PGBOUNCER_APP_USER не задан}"
: "${PGBOUNCER_APP_PASSWORD:?PGBOUNCER_APP_PASSWORD не задан}"

# Формат userlist.txt: значения в двойных кавычках; кавычка внутри значения
# сломала бы разбор, поэтому такой пароль отвергается сразу.
case "${PGBOUNCER_APP_USER}${PGBOUNCER_APP_PASSWORD}" in
  *'"'*)
    echo "pgbouncer: имя или пароль роли приложения содержит двойную кавычку" >&2
    exit 1
    ;;
esac

umask 077
printf '"%s" "%s"\n' "${PGBOUNCER_APP_USER}" "${PGBOUNCER_APP_PASSWORD}" \
  > /run/pgbouncer/userlist.txt

exec pgbouncer /etc/pgbouncer/pgbouncer.ini
