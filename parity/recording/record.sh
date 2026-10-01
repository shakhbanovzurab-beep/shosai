#!/usr/bin/env bash
# Запись фикстур с API черновика — одна команда.
#
#   bash recording/record.sh [аргументы Playwright, например --grep account/]
#
# Шаги:
#   1. экспорт черновика на закреплённом коммите и сборка его фронтенда;
#   2. образ API черновика, его PostgreSQL и Redis во внутренней сети стенда;
#   3. база-шаблон: миграции черновика и засев (recording/seed); пересоздаётся,
#      когда меняется засев, Dockerfile API или коммит черновика;
#   4. рабочая база — свежая копия шаблона, Redis — пустой, API — перезапущен:
#      каждый прогон начинается с одного и того же состояния;
#   5. API стартует под libfaketime в момент гармошки, и это проверяется;
#   6. рекордер (playwright.record.config.ts) пишет fixtures/.
#
# Ничего боевого стенд не видит: сеть draft без выхода наружу, переменные
# окружения заданы явно в compose.yaml, .env черновика не читается.
set -euo pipefail

parity_dir=$(cd "$(dirname "$0")/.." && pwd)
cd "$parity_dir"

if [[ ! -d node_modules/@playwright/test ]]; then
  echo "Нет зависимостей гармошки: выполните npm ci в $parity_dir" >&2
  exit 1
fi

compose=(docker compose -f "$parity_dir/compose.yaml" --profile recording)
db_password=${PARITY_DRAFT_DB_PASSWORD:-parity-local}
psql=("${compose[@]}" exec -T draft-db psql -U draft -d postgres -v ON_ERROR_STOP=1 -qAt)

clock=$(node -p "require('./parity.config.json').clock")
# libfaketime: «@» — часы стартуют с этого момента и идут дальше.
export PARITY_FAKETIME="@$(node -p "new Date('$clock').toISOString().slice(0, 19).replace('T', ' ')")"

bash scripts/build-draft.sh >/dev/null
"${compose[@]}" build draft-api
"${compose[@]}" up -d --wait draft-db draft-redis

seed_hash=$(cat recording/seed/*.py recording/api.Dockerfile parity.config.json | sha256sum | cut -c1-16)
current_hash=$("${psql[@]}" -c "SELECT shobj_description(oid, 'pg_database') FROM pg_database WHERE datname = 'draft_seeded'")

"${compose[@]}" stop draft-api >/dev/null 2>&1 || true
if [[ "$current_hash" != "$seed_hash" ]]; then
  echo "Пересоздаю базу-шаблон черновика (засев $seed_hash)" >&2
  "${psql[@]}" -c "DROP DATABASE IF EXISTS draft" -c "DROP DATABASE IF EXISTS draft_seeded" -c "CREATE DATABASE draft_seeded"
  seeded_url="postgresql+asyncpg://draft:${db_password}@draft-db:5432/draft_seeded"
  "${compose[@]}" run --rm --no-deps -e DATABASE_URL="$seeded_url" draft-api alembic upgrade head
  "${compose[@]}" run --rm --no-deps -e DATABASE_URL="$seeded_url" -e PARITY_CLOCK="$clock" \
    draft-api python /seed/seed.py
  "${psql[@]}" -c "COMMENT ON DATABASE draft_seeded IS '$seed_hash'"
fi

"${psql[@]}" \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'draft'" \
  -c "DROP DATABASE IF EXISTS draft" \
  -c "CREATE DATABASE draft TEMPLATE draft_seeded" >/dev/null
"${compose[@]}" exec -T draft-redis redis-cli FLUSHALL >/dev/null
"${compose[@]}" up -d --wait --force-recreate draft-api

api_date=$("${compose[@]}" exec -T draft-api python -c "import datetime; print(datetime.datetime.now(datetime.UTC).date())")
if [[ "$api_date" != "${clock:0:10}" ]]; then
  echo "API черновика видит дату $api_date вместо ${clock:0:10}: libfaketime не подхватился" >&2
  exit 1
fi

status=0
docker compose -f "$parity_dir/compose.yaml" run --rm harness \
  npx playwright test -c playwright.record.config.ts "$@" || status=$?
# Стенд между прогонами не нужен; база-шаблон остаётся в томе draft-db-data.
"${compose[@]}" stop >/dev/null
exit "$status"
