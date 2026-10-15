#!/usr/bin/env bash
# Выкатка staging из CI (F4 шаг 4, target architecture §17, ADR 0050). Единственная команда ключа
# GitHub Actions: в authorized_keys пользователя deploy она стоит как command="…", поэтому строка,
# которую прислал клиент, приходит в SSH_ORIGINAL_COMMAND и здесь строго проверяется:
#
#   release <github-actor> <образ бэкенда> <образ edge>      токен GHCR задачи CI — первой строкой stdin
#
# Образы — только из GHCR репозитория, с тегом коммита и дайджестом. Токен живёт во временном
# DOCKER_CONFIG до конца pull и на диск плоскости не попадает.
#
# Порядок §17: pull → миграции обоих домов (только расширяющие) → потребители задач и планировщик → api
# → ws → edge. Роль, не ставшая здоровой, или не ответивший через edge /v1/health возвращают прежние
# образы; миграции не откатываются — они совместимы с прежним кодом.
set -euo pipefail

readonly STAGING=/srv/shosai
readonly REGISTRY=ghcr.io/shakhbanovzurab-beep
readonly RELEASES="$STAGING/releases"
readonly CONSUMERS=(workers-critical workers-default workers-bulk workers-meeting scheduler)
readonly WAIT_SECONDS=180

log() { printf '%s release: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >&2; }
fail() {
  log "$*"
  exit 1
}

compose() { docker compose --project-directory "$STAGING" "$@"; }

plane_setting() { sed -n "s/^$1='\(.*\)'$/\1/p" "$STAGING/.env"; }

# Меняет образы в .env плоскости атомарно; остальные строки (домен, источники CSP) не трогает.
write_images() {
  local next="$STAGING/.env.next"
  sed -e "s|^SHOSAI_BACKEND_IMAGE=.*|SHOSAI_BACKEND_IMAGE='$1'|" \
    -e "s|^SHOSAI_EDGE_IMAGE=.*|SHOSAI_EDGE_IMAGE='$2'|" "$STAGING/.env" >"$next"
  chmod 600 "$next"
  mv "$next" "$STAGING/.env"
}

start() { compose up --detach --no-deps --pull never --wait --wait-timeout "$WAIT_SECONDS" "$@"; }

edge_health() {
  local domain
  domain="$(plane_setting SHOSAI_SERVER_NAME)"
  curl --fail --silent --show-error --max-time 10 --resolve "$domain:443:127.0.0.1" \
    "https://$domain/v1/health" >/dev/null
}

record_release() { printf '%s %s %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$backend" "$edge" >>"$RELEASES/history.log"; }

# Шаги §17 после записи новых образов. Каждый шаг проверяется явно: внутри `if !` errexit не действует.
roll_forward() {
  log "миграции обоих домов"
  compose --profile migrate run --rm --pull never migrate upgrade || return 1
  log "потребители задач и планировщик"
  start "${CONSUMERS[@]}" || return 1
  log "api"
  start api || return 1
  log "ws"
  start ws || return 1
  log "edge"
  start edge || return 1
  edge_health
}

# Возврат к прежним образам после сбоя любого шага roll_forward.
restore() {
  log "сбой — возвращаю прежние образы: $previous_backend, $previous_edge"
  write_images "$previous_backend" "$previous_edge"
  if start "${CONSUMERS[@]}" api ws edge && edge_health; then
    log "прежние образы снова работают"
  else
    log "прежние образы не поднялись: нужен человек"
  fi
  record_release failed
}

# Оставляет образы GHCR текущей и прежней выкатки; остальные удаляет, чтобы диск не заполнялся.
prune_images() {
  local name reference
  local keep=" ${backend#*@} ${edge#*@} ${previous_backend#*@} ${previous_edge#*@} "
  for name in shosai-backend shosai-edge; do
    while read -r reference; do
      [[ $keep == *" ${reference#*@} "* ]] && continue
      docker image rm "$reference" >/dev/null || log "не удалось удалить $reference"
    done < <(docker image ls --no-trunc --format '{{.Repository}}@{{.Digest}}' "$REGISTRY/$name" | grep '@sha256:')
  done
}

read -r -a request <<<"${SSH_ORIGINAL_COMMAND:-}"
[[ ${#request[@]} -eq 4 && ${request[0]} == release ]] || fail "ожидалось: release <actor> <backend> <edge>"
actor="${request[1]}"
backend="${request[2]}"
edge="${request[3]}"
[[ $actor =~ ^[A-Za-z0-9][A-Za-z0-9-]{0,38}(\[bot\])?$ ]] || fail "недопустимое имя пользователя GitHub"
registry_pattern="${REGISTRY//./\\.}"
for image in "backend:$backend" "edge:$edge"; do
  pattern="^$registry_pattern/shosai-${image%%:*}:[0-9a-f]{40}@sha256:[0-9a-f]{64}$"
  [[ ${image#*:} =~ $pattern ]] || fail "недопустимый образ: ${image#*:}"
done
commit="${backend%@*}"
commit="${commit##*:}"
[[ $edge == *":$commit@"* ]] || fail "образы собраны из разных коммитов"
IFS= read -r token || fail "нет токена GHCR на stdin"
[[ -n $token ]] || fail "пустой токен GHCR"

install -d -m 700 "$RELEASES"
exec 9>"$RELEASES/.lock"
flock --wait 900 9 || fail "другая выкатка не закончилась за 15 минут"

log "коммит $commit: загружаю образы"
docker_config="$(mktemp -d)"
trap 'rm -rf "$docker_config"' EXIT
printf '%s\n' "$token" | DOCKER_CONFIG="$docker_config" docker login ghcr.io --username "$actor" --password-stdin >/dev/null
unset token
DOCKER_CONFIG="$docker_config" docker pull --quiet "$backend" >/dev/null
DOCKER_CONFIG="$docker_config" docker pull --quiet "$edge" >/dev/null
rm -rf "$docker_config"

previous_backend="$(plane_setting SHOSAI_BACKEND_IMAGE)"
previous_edge="$(plane_setting SHOSAI_EDGE_IMAGE)"
if [[ $previous_backend == "$backend" && $previous_edge == "$edge" ]]; then
  log "коммит $commit уже выкачен"
  exit 0
fi
printf "SHOSAI_BACKEND_IMAGE='%s'\nSHOSAI_EDGE_IMAGE='%s'\n" "$previous_backend" "$previous_edge" >"$RELEASES/previous.env"
write_images "$backend" "$edge"
if ! roll_forward; then
  restore
  exit 1
fi
record_release released
prune_images
log "коммит $commit выкачен"
