#!/usr/bin/env bash
# Первичная настройка локального сервера PostgreSQL, заменяющего управляемую БД
# одного дома (RU или EU) — target architecture §4.1, §6, §7.
#
# Запускается официальным entrypoint образа один раз, на пустом томе, от имени
# суперпользователя. Повторно не выполняется: чтобы применить изменения, нужен
# сброс окружения (`scripts/local-env.sh reset`).
#
# Создаёт то, что на управляемом сервере делает провайдер или администратор:
#   - роль миграций `shosai_migrator` — владелец баз и схемы, без SUPERUSER и
#     BYPASSRLS, ходит в PostgreSQL напрямую;
#   - роль приложения `shosai_app` — без SUPERUSER и BYPASSRLS, ходит через
#     PgBouncer; под ней RLS действует по-настоящему (§7);
#   - базу дома `shosai` и подготовленные тестовые базы `shosai_test_<N>`
#     для параллельных прогонов (CLAUDE.md, «Test database»);
#   - расширение `vector` в каждой базе: оно не trusted, и роль миграций создать
#     его не может.
# Права на таблицы роли приложения выдают миграции, а не этот скрипт.
set -Eeuo pipefail

readonly MIGRATOR_ROLE="shosai_migrator"
readonly APP_ROLE="shosai_app"
readonly HOME_DATABASE="shosai"
readonly TEST_DATABASE_PREFIX="shosai_test_"
readonly MAX_TEST_DATABASES=64

: "${POSTGRES_USER:?POSTGRES_USER не задан}"
: "${SHOSAI_HOME:?SHOSAI_HOME не задан: ожидается ru или eu}"
: "${SHOSAI_MIGRATOR_PASSWORD:?SHOSAI_MIGRATOR_PASSWORD не задан}"
: "${SHOSAI_APP_PASSWORD:?SHOSAI_APP_PASSWORD не задан}"
: "${SHOSAI_TEST_DATABASE_COUNT:?SHOSAI_TEST_DATABASE_COUNT не задан}"

case "${SHOSAI_HOME}" in
  ru)
    home_label="Russian home"
    home_description="Russian home"
    ;;
  eu)
    home_label="EU home"
    home_description="EU home; also holds the directory"
    ;;
  *)
    echo "init-home: неизвестный дом '${SHOSAI_HOME}', ожидается ru или eu" >&2
    exit 1
    ;;
esac

if ! [[ "${SHOSAI_TEST_DATABASE_COUNT}" =~ ^[0-9]+$ ]] \
  || (( SHOSAI_TEST_DATABASE_COUNT < 1 || SHOSAI_TEST_DATABASE_COUNT > MAX_TEST_DATABASES )); then
  echo "init-home: SHOSAI_TEST_DATABASE_COUNT должен быть целым от 1 до ${MAX_TEST_DATABASES}" >&2
  exit 1
fi

# Пароли и имена передаются переменными psql: подстановка `:'name'` экранирует
# значение, поэтому SQL не собирается конкатенацией строк.
run_sql() {
  local database="$1"
  shift
  psql --no-psqlrc --no-password --set=ON_ERROR_STOP=1 \
    --username="${POSTGRES_USER}" --dbname="${database}" "$@"
}

create_roles() {
  run_sql postgres \
    --set=migrator_role="${MIGRATOR_ROLE}" \
    --set=app_role="${APP_ROLE}" \
    --set=migrator_password="${SHOSAI_MIGRATOR_PASSWORD}" \
    --set=app_password="${SHOSAI_APP_PASSWORD}" <<'SQL'
CREATE ROLE :"migrator_role" LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS
  PASSWORD :'migrator_password';
CREATE ROLE :"app_role" LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS
  PASSWORD :'app_password';
SQL
}

create_database() {
  local database="$1" description="$2"
  run_sql postgres \
    --set=database="${database}" \
    --set=description="${description}" \
    --set=migrator_role="${MIGRATOR_ROLE}" \
    --set=app_role="${APP_ROLE}" <<'SQL'
CREATE DATABASE :"database" OWNER :"migrator_role";
COMMENT ON DATABASE :"database" IS :'description';
REVOKE ALL ON DATABASE :"database" FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE :"database" TO :"app_role";
SQL
  run_sql "${database}" <<'SQL'
CREATE EXTENSION vector;
SQL
}

create_roles
create_database "${HOME_DATABASE}" "Shosai ${home_description} (local)"
for (( slot = 1; slot <= SHOSAI_TEST_DATABASE_COUNT; slot++ )); do
  create_database "${TEST_DATABASE_PREFIX}${slot}" \
    "Prepared test database ${slot} of the ${home_label} (local)"
done

echo "init-home: дом ${SHOSAI_HOME} готов, тестовых баз: ${SHOSAI_TEST_DATABASE_COUNT}"
