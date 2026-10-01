#!/usr/bin/env bash
# Сборка фронтенда черновика из экспорта (scripts/export-draft.sh).
#
# Собирается в контейнере стенда сравнения: в нём Node 24, тот же мажор, что в
# Dockerfile черновика. Результат — `<экспорт>/dist`. Пересборка — только если
# сборки ещё нет: экспорт закреплён на коммите и не меняется.
set -euo pipefail

parity_dir=$(cd "$(dirname "$0")/.." && pwd)
export_dir=$(bash "$parity_dir/scripts/export-draft.sh")
relative=${export_dir#"$parity_dir"/}

if [[ -f "$export_dir/dist/index.html" ]]; then
  echo "$export_dir/dist"
  exit 0
fi

# Каталог /repo/parity в контейнере — это parity/ на хосте (compose.yaml, сервис harness).
docker compose -f "$parity_dir/compose.yaml" run --rm --no-deps harness \
  bash -c "cd '/repo/parity/$relative/frontend' && npm ci --no-audit --no-fund && npx vite build --outDir ../dist --emptyOutDir" >&2

echo "$export_dir/dist"
