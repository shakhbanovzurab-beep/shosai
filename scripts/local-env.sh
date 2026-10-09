#!/usr/bin/env bash
# Локальное окружение Shosai (compose.dev.yaml): запуск, остановка, сброс.
# Подробности и соответствие домов серверам — docs/development.md.
#
#   scripts/local-env.sh up            запустить и дождаться готовности всех сервисов
#   scripts/local-env.sh down          остановить; данные в томах сохраняются
#   scripts/local-env.sh reset [--yes] удалить тома ЭТОГО проекта и запустить заново
#   scripts/local-env.sh status        состояние сервисов и их health checks
set -Eeuo pipefail

REPOSITORY_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly REPOSITORY_ROOT
readonly COMPOSE_FILE="${REPOSITORY_ROOT}/compose.dev.yaml"
# Совпадает с `name:` в compose.dev.yaml; по нему отбираются тома для сброса.
readonly PROJECT_NAME="shosai-local"
readonly WAIT_TIMEOUT_SECONDS=180

compose() {
  docker compose --file "${COMPOSE_FILE}" --project-name "${PROJECT_NAME}" "$@"
}

start() {
  compose up --detach --wait --wait-timeout "${WAIT_TIMEOUT_SECONDS}"
  compose ps
}

stop() {
  compose down --remove-orphans
}

project_volumes() {
  docker volume ls --quiet --filter "label=com.docker.compose.project=${PROJECT_NAME}"
}

reset() {
  local confirmed="${1:-}"
  if [[ -n "${confirmed}" && "${confirmed}" != "--yes" ]]; then
    echo "local-env: неизвестный флаг '${confirmed}', ожидается --yes" >&2
    exit 2
  fi

  local volume_list
  volume_list="$(project_volumes)"
  if [[ -n "${volume_list}" ]]; then
    local -a volumes
    mapfile -t volumes <<< "${volume_list}"
    echo "Будут безвозвратно удалены тома проекта ${PROJECT_NAME}:"
    printf '  %s\n' "${volumes[@]}"
    echo "Это все локальные данные: базы обоих домов, Valkey, Qdrant и бакеты S3."
    if [[ "${confirmed}" != "--yes" ]]; then
      if [[ ! -t 0 ]]; then
        echo "local-env: нет терминала для подтверждения; запустите с --yes" >&2
        exit 1
      fi
      local answer
      read -r -p "Удалить? Введите yes: " answer
      if [[ "${answer}" != "yes" ]]; then
        echo "Сброс отменён."
        exit 1
      fi
    fi
  fi

  # `down --volumes` удаляет только тома, объявленные в этом проекте Compose.
  compose down --volumes --remove-orphans
  start
}

usage() {
  sed -n '5,8p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

main() {
  local command="${1:-}"
  case "${command}" in
    up) start ;;
    down) stop ;;
    reset) reset "${2:-}" ;;
    status) compose ps ;;
    -h | --help | help) usage ;;
    *)
      usage >&2
      exit 2
      ;;
  esac
}

main "$@"
