#!/usr/bin/env bash
# Экспорт черновика на закреплённом коммите в кэш стенда сравнения.
#
# Рабочее дерево черновика не трогается: `git archive` читает объекты
# репозитория, а не файлы на диске. Поэтому незакоммиченные правки черновика в
# эталон не попадают, и экспорт одного коммита всегда одинаков.
#
# Печатает путь к экспорту. Повторный вызов с тем же коммитом и тем же списком
# путей ничего не делает; изменённый список пересобирает экспорт.
set -euo pipefail

parity_dir=$(cd "$(dirname "$0")/.." && pwd)
commit=$(node -p "require('$parity_dir/parity.config.json').draft.commit")
draft_repo=${DRAFT_REPO:-/root/whisperer}
target="$parity_dir/.cache/draft/$commit"

# compose.yaml ссылается на `.cache/draft/current`: так ему не нужно знать коммит.
link_current() {
  ln -sfn -- "$commit" "$parity_dir/.cache/draft/current"
}

# Только то, что нужно фронтенду и API черновика во время записи и съёмки.
# Лендинг, справка и SEO-файлы (≈ 120 МБ) не нужны ни тому, ни другому. Корневые
# иконки страница итога встречи берёт из корня сайта, как у бэкенда черновика.
paths=(
  frontend
  backend/src
  backend/alembic
  backend/alembic.ini
  backend/pyproject.toml
  backend/requirements.txt
  backend/assets
  backend/data
  backend/trust
  backend/static/email
  backend/static/landing/fonts
  backend/static/webfonts
  backend/static/favicon.svg
  backend/static/favicon.ico
  backend/static/favicon-32.png
  backend/static/apple-touch-icon.png
  backend/static/icon-192.png
  backend/static/icon-512.png
  backend/static/icon-maskable-512.png
)
# Метка готовности хранит отпечаток списка: правка списка не прячется за кэшем.
fingerprint=$(printf '%s\n' "${paths[@]}" | sha256sum | cut -c1-16)

if [[ -f "$target/.complete" && "$(cat "$target/.complete")" == "$fingerprint" ]]; then
  link_current
  echo "$target"
  exit 0
fi

if ! git -C "$draft_repo" cat-file -e "$commit^{commit}" 2>/dev/null; then
  echo "Коммит черновика $commit не найден в $draft_repo (задайте DRAFT_REPO)" >&2
  exit 1
fi

# Сборка во временный каталог и атомарная замена: прерванный экспорт не должен
# выглядеть готовым при следующем запуске.
staging="$target.partial"
rm -rf -- "$staging"
mkdir -p -- "$staging"

git -C "$draft_repo" archive "$commit" "${paths[@]}" | tar -x -C "$staging"

echo "$fingerprint" > "$staging/.complete"
rm -rf -- "$target"
mv -- "$staging" "$target"
link_current
echo "$target"
