#!/bin/sh
# Бот и чат мониторинга для проверки доставки из локального Alertmanager (F5 шаг 6). Берёт
# MONITORING_TELEGRAM_BOT_TOKEN и MONITORING_TELEGRAM_CHAT_ID из .env в корне репозитория и кладёт
# их в deploy/local/secrets/alertmanager (каталог в .gitignore) для пользователя nobody, под которым
# работает Alertmanager. Адрес heartbeat не копируется никогда: его пингует только staging.
# Без этих файлов локальный стек никому не пишет — после проверки их нужно удалить.
#
#   deploy/local/alertmanager-secrets.sh            # положить; затем перезапустить alertmanager
#   deploy/local/alertmanager-secrets.sh --remove   # удалить; затем перезапустить alertmanager
set -eu

here=$(cd "$(dirname "$0")" && pwd)
dir="$here/secrets/alertmanager"
env_file="$here/../../.env"

if [ "${1:-}" = "--remove" ]; then
  rm -rf "$dir"
  echo "секреты Alertmanager удалены: $dir"
  exit 0
fi

value() {
  sed -n "s/^$1=//p" "$env_file" | tail -n 1 | tr -d "\"'\r"
}

token=$(value MONITORING_TELEGRAM_BOT_TOKEN)
chat=$(value MONITORING_TELEGRAM_CHAT_ID)
if [ -z "$token" ] || [ -z "$chat" ]; then
  echo "в $env_file нет MONITORING_TELEGRAM_BOT_TOKEN или MONITORING_TELEGRAM_CHAT_ID" >&2
  exit 1
fi

umask 077
mkdir -p "$dir"
printf '%s' "$token" > "$dir/telegram-bot-token"
printf '%s' "$chat" > "$dir/telegram-chat-id"
chmod 0755 "$here/secrets" "$dir"
chmod 0400 "$dir/telegram-bot-token" "$dir/telegram-chat-id"
chown 65534:65534 "$dir/telegram-bot-token" "$dir/telegram-chat-id"
echo "секреты Alertmanager положены: $dir"
