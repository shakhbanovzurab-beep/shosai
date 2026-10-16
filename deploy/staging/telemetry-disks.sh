#!/bin/sh
# Файловые системы заданного размера для данных Loki и Tempo на staging (план F5 §3.4, F5-D3).
# Loki и Tempo удаляют данные только по сроку; потолок даёт файловая система: файл-образ, смонтированный
# юнитом systemd в /srv/shosai/telemetry/<имя>. Node exporter видит её как диск, поэтому тикет диска на
# 80% следит и за потолком. Повторный запуск ничего не пересоздаёт и данных не трогает.
#
#   sh telemetry-disks.sh /srv/shosai        # от root на сервере staging
set -eu
target="${1:?каталог staging, например /srv/shosai}"
units=/etc/systemd/system
here="$(dirname "$0")"
# uid процессов Loki и Tempo в их образах.
owner=10001
install -d -m 755 "$target/telemetry"
for disk in loki:5G tempo:3G; do
  name="${disk%%:*}"
  size="${disk#*:}"
  image="$target/telemetry/$name.img"
  mount_point="$target/telemetry/$name"
  if [ ! -e "$image" ]; then
    fallocate -l "$size" "$image"
    chmod 600 "$image"
    mkfs.ext4 -q -L "shosai-$name" -m 0 "$image"
  fi
  install -d -m 750 "$mount_point"
  unit="$(systemd-escape --path --suffix=mount "$mount_point")"
  sed -e "s|__IMAGE__|$image|" -e "s|__WHERE__|$mount_point|" \
    "$here/systemd/shosai-telemetry.mount.in" > "$units/$unit"
  systemctl daemon-reload
  systemctl enable --now "$unit"
  chown "$owner:$owner" "$mount_point"
  chmod 750 "$mount_point"
done
install -d -m 755 "$target/telemetry/probe-targets"
