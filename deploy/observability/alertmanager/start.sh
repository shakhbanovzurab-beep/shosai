#!/bin/sh
# Запуск Alertmanager Shosai: конфигурация и шаблон рендерятся в /tmp/alertmanager, секреты с хоста
# копируются туда же (корень контейнера только на чтение). Каталог /run/shosai-alertmanager с хоста:
#   telegram-bot-token, telegram-chat-id — бот и чат мониторинга (F5-D4); нет — доставка выключена;
#   heartbeat-url — адрес внешнего heartbeat (F5-D2); нет — Watchdog никуда не пингует.
# GRAFANA_ROOT_URL и SHOSAI_RUNBOOK_URL — начала ссылок в сообщениях.
#
#   start.sh [флаги alertmanager]     # запуск
#   start.sh --render-only            # только рендер (проверка конфигурации в CI)
set -eu

source_dir=/etc/alertmanager/shosai
secrets=/run/shosai-alertmanager
out=/tmp/alertmanager
: "${GRAFANA_ROOT_URL:?адрес Grafana не задан}"
: "${SHOSAI_RUNBOOK_URL:?адрес runbook не задан}"

umask 077
mkdir -p "$out"

telegram=blackhole
if [ -s "$secrets/telegram-bot-token" ] && [ -s "$secrets/telegram-chat-id" ]; then
  telegram=telegram
  cp "$secrets/telegram-bot-token" "$secrets/telegram-chat-id" "$out/"
else
  echo "start.sh: нет токена или чата Telegram — оповещения не доставляются" >&2
fi

heartbeat=blackhole
if [ -s "$secrets/heartbeat-url" ]; then
  heartbeat=heartbeat
  cp "$secrets/heartbeat-url" "$out/"
else
  echo "start.sh: нет адреса heartbeat — Watchdog никуда не пингует" >&2
fi

sed -e "s|__TELEGRAM__|$telegram|g" -e "s|__HEARTBEAT__|$heartbeat|g" \
  "$source_dir/alertmanager.yml" > "$out/alertmanager.yml"
sed -e "s|__GRAFANA_URL__|$GRAFANA_ROOT_URL|g" -e "s|__RUNBOOK_URL__|$SHOSAI_RUNBOOK_URL|g" \
  "$source_dir/telegram.tmpl" > "$out/telegram.tmpl"

if [ "${1:-}" = "--render-only" ]; then
  exit 0
fi
exec /bin/alertmanager --config.file="$out/alertmanager.yml" --storage.path=/alertmanager "$@"
