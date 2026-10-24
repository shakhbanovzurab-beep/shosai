#!/usr/bin/env bash
# Выкатка и откат staging (F4 шаги 4–5, target architecture §17, ADR 0050). Две команды:
#
#   release <github-actor> <образ бэкенда> <образ edge> [<образ наблюдаемости>]
#                                         — от CI по SSH; токен GHCR задачи — первой строкой stdin
#   rollback                              — человек на сервере: sudo -u deploy …/release.sh rollback
#
# Для ключа GitHub Actions скрипт — единственная команда: в authorized_keys пользователя deploy он стоит
# как command="…", поэтому строка клиента приходит в SSH_ORIGINAL_COMMAND и строго проверяется. По SSH
# доступен только release: образы из GHCR репозитория, с тегом коммита и дайджестом. Токен живёт во
# временном DOCKER_CONFIG до конца pull и на диск плоскости не попадает.
#
# Порядок §17: pull → стек наблюдаемости с конфигурацией коммита (F5-D6; загруженные правила должны
# совпасть с правилами образа) → миграции обоих домов (только расширяющие) → потребители задач и
# планировщик → воркер ходов Leo → api → ws → edge. Воркер ходов, api и ws сменяются без простоя: новая
# копия становится здоровой раньше, чем старая получает SIGTERM; старый воркер ходов дослушивает начатые
# ходы до 190 с (AG-D12). Роль, не ставшая здоровой, или не ответивший через edge /v1/health возвращают
# прежние образы; миграции не откатываются — они совместимы с прежним кодом. Откат — та же смена без
# миграций к образам releases/previous.env; повторный откат возвращает откаченные образы.
set -euo pipefail

readonly STAGING=/srv/shosai
readonly REGISTRY=ghcr.io/shakhbanovzurab-beep
readonly RELEASES="$STAGING/releases"
readonly OBSERVABILITY="$STAGING/observability"
readonly PLANE_NETWORK=shosai-staging_plane
readonly CONSUMERS=(workers-critical workers-default workers-bulk workers-meeting scheduler)
# Ходы Leo: передаётся без простоя, как api, и останавливается со своей отсрочкой (compose.yaml).
readonly AGENT_WORKERS=workers-agent
readonly AGENT_STOP_SECONDS=200
readonly WAIT_SECONDS=180
# Edge перечитывает адреса api и ws раз в 10 с (resolver … valid=10s): за это время он узнаёт новую копию.
readonly EDGE_RESOLVE_SECONDS=12
# Роль дослушивает запросы до 20 с (backend README, «Stop»); дольше — её останавливают силой.
readonly STOP_SECONDS=30

log() { printf '%s release: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >&2; }
fail() {
  log "$*"
  exit 1
}

compose() { docker compose --project-directory "$STAGING" "$@"; }
# Стек наблюдаемости — свой проект; образ конфигурации — в .env его каталога. Файлы названы явно:
# COMPOSE_FILE из .env Compose отсчитывает от текущего каталога, а не от каталога проекта.
telemetry() {
  docker compose --project-directory "$OBSERVABILITY" \
    -f "$OBSERVABILITY/compose.yaml" -f "$OBSERVABILITY/compose.staging.yaml" "$@"
}

plane_setting() { sed -n "s/^$1='\(.*\)'$/\1/p" "$STAGING/.env"; }

images_line() {
  printf "SHOSAI_BACKEND_IMAGE='%s'\nSHOSAI_EDGE_IMAGE='%s'\n" "$1" "$2"
  [[ -z $3 ]] || printf "SHOSAI_OBSERVABILITY_IMAGE='%s'\n" "$3"
}

observability_setting() { sed -n "s/^SHOSAI_OBSERVABILITY_IMAGE='\(.*\)'$/\1/p" "$OBSERVABILITY/.env" 2>/dev/null || true; }

# Меняет образ конфигурации в .env стека атомарно; COMPOSE_FILE не трогает.
write_observability() {
  local next="$OBSERVABILITY/.env.next"
  sed -e "s|^SHOSAI_OBSERVABILITY_IMAGE=.*|SHOSAI_OBSERVABILITY_IMAGE='$1'|" "$OBSERVABILITY/.env" >"$next"
  chmod 600 "$next"
  mv "$next" "$OBSERVABILITY/.env"
}

# Сколько правил загрузили Prometheus и правитель Loki — по их API из одноразового контейнера в сети
# плоскости (wget образа Prometheus имён соседних служб не разрешает).
loaded_rules() {
  docker run --rm --network "$PLANE_NETWORK" busybox:1.37.0 wget -qO- "$1" | python3 -c \
    'import json, sys; print(sum(len(g["rules"]) for g in json.load(sys.stdin)["data"]["groups"]))'
}

# Сколько правил в образе конфигурации: файлы Prometheus проверяет promtool, файлы Loki — счёт строк.
expected_prometheus_rules() {
  telemetry exec -T prometheus sh -c 'promtool check rules /etc/prometheus/rules/*.yml \
    /etc/prometheus/rules/generated/*.recording.json /etc/prometheus/rules/generated/*.alerts.json' |
    sed -n 's/.*SUCCESS: \([0-9]*\) rules found.*/\1/p' | awk '{ total += $1 } END { print total + 0 }'
}

expected_loki_rules() {
  docker run --rm --network none --mount "type=image,source=$1,target=/rules,image-subpath=loki/rules" \
    busybox:1.37.0 sh -c 'cat /rules/*.yml' | grep -cE '^[[:space:]]*- (alert|record):'
}

# Стек с образом конфигурации коммита: службы, что его читают, пересоздаются; затем правила, которые
# загрузились, сверяются с правилами образа. Правитель Loki перечитывает правила раз в минуту.
start_observability() {
  local image="$1" expected loaded attempt
  [[ -n $image ]] || return 0
  [[ -f $OBSERVABILITY/.env ]] || { log "нет $OBSERVABILITY/.env: стек наблюдаемости не установлен"; return 1; }
  write_observability "$image"
  telemetry up --detach --pull never --wait --wait-timeout "$WAIT_SECONDS" --remove-orphans || return 1
  expected="$(expected_prometheus_rules)" || return 1
  loaded="$(loaded_rules http://prometheus:9090/api/v1/rules)" || return 1
  [[ $expected -gt 0 && $expected == "$loaded" ]] || { log "Prometheus: правил загружено $loaded из $expected"; return 1; }
  expected="$(expected_loki_rules "$image")" || return 1
  for attempt in $(seq 1 18); do
    loaded="$(loaded_rules http://loki:3100/prometheus/api/v1/rules)" || loaded=0
    [[ $loaded == "$expected" ]] && break
    [[ $attempt == 18 ]] && { log "Loki: правил загружено $loaded из $expected"; return 1; }
    sleep 5
  done
  log "наблюдаемость: правил Prometheus $(expected_prometheus_rules), Loki $expected — все загружены"
}

# Меняет образы в .env плоскости атомарно; остальные строки (домен, источники CSP) не трогает.
write_images() {
  local next="$STAGING/.env.next"
  sed -e "s|^SHOSAI_BACKEND_IMAGE=.*|SHOSAI_BACKEND_IMAGE='$1'|" \
    -e "s|^SHOSAI_EDGE_IMAGE=.*|SHOSAI_EDGE_IMAGE='$2'|" "$STAGING/.env" >"$next"
  chmod 600 "$next"
  mv "$next" "$STAGING/.env"
}

start() { compose up --detach --no-deps --pull never --wait --wait-timeout "$WAIT_SECONDS" "$@"; }

# Смена роли без простоя: вторая копия с новым образом рядом со старой, пауза, пока edge узнаёт её адрес,
# затем старая останавливается (запрос, не дошедший до неё, edge повторяет на новой) и удаляется. Второй
# аргумент — отсрочка остановки старой копии в секундах.
hand_over() {
  local service="$1" stop_seconds="${2:-$STOP_SECONDS}" old
  old="$(compose ps --quiet "$service")"
  if [[ -z $old || $(docker inspect --format '{{.Config.Image}}' "$old") == "$backend" ]]; then
    start "$service"
    return
  fi
  compose up --detach --no-deps --pull never --no-recreate --wait --wait-timeout "$WAIT_SECONDS" \
    --scale "$service=2" "$service" || return 1
  sleep "$EDGE_RESOLVE_SECONDS"
  docker stop --time "$stop_seconds" "$old" >/dev/null || return 1
  docker rm "$old" >/dev/null
}

edge_health() {
  local domain
  domain="$(plane_setting SHOSAI_SERVER_NAME)"
  curl --fail --silent --show-error --max-time 10 --resolve "$domain:443:127.0.0.1" \
    "https://$domain/v1/health" >/dev/null
}

record_release() { printf '%s %s %s %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$backend" "$edge" "${observability:--}" >>"$RELEASES/history.log"; }

# Смена ролей в порядке §17. Каждый шаг проверяется явно: внутри `if !` и `&&` errexit не действует.
switch_roles() {
  log "потребители задач и планировщик"
  start "${CONSUMERS[@]}" || return 1
  log "воркер ходов Leo"
  hand_over "$AGENT_WORKERS" "$AGENT_STOP_SECONDS" || return 1
  log "api"
  hand_over api || return 1
  log "ws"
  hand_over ws || return 1
  log "edge"
  start edge || return 1
  edge_health
}

roll_forward() {
  log "стек наблюдаемости"
  start_observability "$observability" || return 1
  log "миграции обоих домов"
  compose --profile migrate run --rm --pull never migrate upgrade || return 1
  switch_roles
}

# Возврат к образам, что работали до этой смены, после сбоя любого её шага.
restore() {
  log "сбой — возвращаю прежние образы: $previous_backend, $previous_edge"
  write_images "$previous_backend" "$previous_edge"
  if [[ -n $observability && $previous_observability != "$observability" ]]; then
    if docker image inspect "$previous_observability" >/dev/null 2>&1; then
      start_observability "$previous_observability" || log "прежняя конфигурация наблюдаемости не поднялась"
    else
      log "прежней конфигурации наблюдаемости нет: стек остаётся как есть"
    fi
  fi
  if start "${CONSUMERS[@]}" "$AGENT_WORKERS" api ws edge && edge_health; then
    log "прежние образы снова работают"
  else
    log "прежние образы не поднялись: нужен человек"
  fi
}

# Оставляет образы GHCR текущей и прежней выкатки; остальные удаляет, чтобы диск не заполнялся.
prune_images() {
  local name reference
  local keep=" ${backend#*@} ${edge#*@} ${previous_backend#*@} ${previous_edge#*@} "
  keep+="${observability#*@} ${previous_observability#*@} "
  for name in shosai-backend shosai-edge shosai-observability; do
    while read -r reference; do
      [[ $keep == *" ${reference#*@} "* ]] && continue
      docker image rm "$reference" >/dev/null || log "не удалось удалить $reference"
    done < <(docker image ls --no-trunc --format '{{.Repository}}@{{.Digest}}' "$REGISTRY/$name" | grep '@sha256:')
  done
}

# Запрос по SSH проверяется до любого действия; токен читается сразу, пока stdin открыт.
read_release_request() {
  [[ ${#request[@]} -eq 4 || ${#request[@]} -eq 5 ]] || fail "ожидалось: release <actor> <backend> <edge> [<observability>]"
  actor="${request[1]}"
  backend="${request[2]}"
  edge="${request[3]}"
  observability="${request[4]:-}"
  [[ $actor =~ ^[A-Za-z0-9][A-Za-z0-9-]{0,38}(\[bot\])?$ ]] || fail "недопустимое имя пользователя GitHub"
  local image pattern registry_pattern="${REGISTRY//./\\.}"
  local images=("backend:$backend" "edge:$edge")
  [[ -z $observability ]] || images+=("observability:$observability")
  for image in "${images[@]}"; do
    pattern="^$registry_pattern/shosai-${image%%:*}:[0-9a-f]{40}@sha256:[0-9a-f]{64}$"
    [[ ${image#*:} =~ $pattern ]] || fail "недопустимый образ: ${image#*:}"
  done
  commit="${backend%@*}"
  commit="${commit##*:}"
  [[ $edge == *":$commit@"* && ${observability:-":$commit@"} == *":$commit@"* ]] ||
    fail "образы собраны из разных коммитов"
  IFS= read -r token || fail "нет токена GHCR на stdin"
  [[ -n $token ]] || fail "пустой токен GHCR"
}

pull_images() {
  log "коммит $commit: загружаю образы"
  docker_config="$(mktemp -d)"
  trap 'rm -rf "$docker_config"' EXIT
  printf '%s\n' "$token" | DOCKER_CONFIG="$docker_config" docker login ghcr.io --username "$actor" --password-stdin >/dev/null
  unset token
  DOCKER_CONFIG="$docker_config" docker pull --quiet "$backend" >/dev/null
  DOCKER_CONFIG="$docker_config" docker pull --quiet "$edge" >/dev/null
  [[ -z $observability ]] || DOCKER_CONFIG="$docker_config" docker pull --quiet "$observability" >/dev/null
  rm -rf "$docker_config"
}

# По SSH команду задаёт только строка клиента: аргументов у принудительной команды нет.
if [[ -n ${SSH_CONNECTION:-} ]]; then
  read -r -a request <<<"${SSH_ORIGINAL_COMMAND:-}"
else
  request=("$@")
fi
action="${request[0]:-}"
case "$action" in
  release) read_release_request ;;
  rollback)
    [[ -z ${SSH_CONNECTION:-} && ${#request[@]} -eq 1 ]] || fail "откат запускает человек на сервере: release.sh rollback"
    ;;
  *) fail "ожидалось: release <actor> <backend> <edge> или rollback" ;;
esac
[[ $(id -un) == deploy ]] || fail "запускать от deploy: sudo -u deploy $0 $action"

install -d -m 700 "$RELEASES"
exec 9>"$RELEASES/.lock"
flock --wait 900 9 || fail "другая выкатка не закончилась за 15 минут"

previous_backend="$(plane_setting SHOSAI_BACKEND_IMAGE)"
previous_edge="$(plane_setting SHOSAI_EDGE_IMAGE)"
previous_observability="$(observability_setting)"
if [[ $action == rollback ]]; then
  [[ -f $RELEASES/previous.env ]] || fail "нет прежней выкатки: releases/previous.env"
  backend="$(sed -n "s/^SHOSAI_BACKEND_IMAGE='\(.*\)'$/\1/p" "$RELEASES/previous.env")"
  edge="$(sed -n "s/^SHOSAI_EDGE_IMAGE='\(.*\)'$/\1/p" "$RELEASES/previous.env")"
  observability="$(sed -n "s/^SHOSAI_OBSERVABILITY_IMAGE='\(.*\)'$/\1/p" "$RELEASES/previous.env")"
  docker image inspect "$backend" "$edge" ${observability:+"$observability"} >/dev/null || fail "прежних образов нет на сервере"
  log "откат к $backend, $edge${observability:+, $observability}"
else
  pull_images
  if [[ $previous_backend == "$backend" && $previous_edge == "$edge" && ${observability:-$previous_observability} == "$previous_observability" ]]; then
    log "коммит $commit уже выкачен"
    exit 0
  fi
fi
write_images "$backend" "$edge"
if [[ $action == rollback ]]; then
  { start_observability "$observability" && switch_roles; } && outcome=rolled-back || outcome=failed
else
  roll_forward && outcome=released || outcome=failed
fi
if [[ $outcome == failed ]]; then
  restore
  record_release failed
  exit 1
fi
# Прежней становится выкатка до этой смены; неудачная попытка её не трогает.
images_line "$previous_backend" "$previous_edge" "$previous_observability" >"$RELEASES/previous.env"
record_release "$outcome"
prune_images
log "готово: $outcome, $backend, $edge${observability:+, $observability}"
