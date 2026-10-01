#!/usr/bin/env bash
# Стенд сравнения — одна команда:
#
#   bash scripts/parity.sh baseline [аргументы Playwright]   снять эталон с черновика
#   bash scripts/parity.sh verify   [аргументы Playwright]   повторяемость: черновик против эталона
#   bash scripts/parity.sh compare  [аргументы Playwright]   v2 против эталона
#
# Срез выбирает свои экраны по идентификатору состояния:
#   bash scripts/parity.sh compare --grep "billing\."
#
# Съёмка идёт в закреплённом контейнере Playwright (compose.yaml, сервис harness):
# браузер и его шрифты одинаковы на любой машине и в CI. Хранилище эталона —
# переменные PARITY_S3_* (README.md); compare и verify без них работают, если
# локальная копия эталона уже совпадает с манифестом.
set -euo pipefail

parity_dir=$(cd "$(dirname "$0")/.." && pwd)
command=${1:-}
case "$command" in
  baseline | verify)
    # Черновик нужен как цель съёмки: экспорт закреплённого коммита и его сборка.
    bash "$parity_dir/scripts/build-draft.sh" >/dev/null
    ;;
  compare) ;;
  *)
    echo "Использование: scripts/parity.sh baseline|verify|compare [аргументы Playwright]" >&2
    exit 2
    ;;
esac
shift

if [[ ! -d "$parity_dir/node_modules/@playwright/test" ]]; then
  echo "Нет зависимостей стенда: выполните npm ci в $parity_dir" >&2
  exit 1
fi

docker compose -f "$parity_dir/compose.yaml" run --rm harness node src/cli/parity.ts "$command" "$@"
