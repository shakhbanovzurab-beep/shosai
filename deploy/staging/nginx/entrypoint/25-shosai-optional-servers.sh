#!/bin/sh
# Необязательные серверы edge: блок Grafana — только при заданном SHOSAI_GRAFANA_SERVER_NAME
# (staging), сигнализация и TURN LiveKit — при заданных своих именах; иначе подставленный файл
# удаляется до старта NGINX. Запускается после подстановки
# шаблонов (20-envsubst-on-templates.sh образа).
set -eu
if [ -z "${SHOSAI_GRAFANA_SERVER_NAME:-}" ]; then
  rm -f "${NGINX_ENVSUBST_OUTPUT_DIR:?}/conf.d/grafana.conf"
fi
# Сигнализация LiveKit на своём имени (meetings A15) — только при заданном имени.
if [ -z "${SHOSAI_RTC_SERVER_NAME:-}" ]; then
  rm -f "${NGINX_ENVSUBST_OUTPUT_DIR:?}/conf.d/rtc.conf"
fi
# TURN/TLS LiveKit за 443 (meetings A14) — только при заданном имени TURN.
if [ -z "${SHOSAI_TURN_SERVER_NAME:-}" ]; then
  rm -f "${NGINX_ENVSUBST_OUTPUT_DIR:?}/stream-routes/turn.map" "${NGINX_ENVSUBST_OUTPUT_DIR:?}/stream/turn.conf"
fi
# Скачивание через edge (FL-D9) — только когда заданы бакеты обоих домов.
if [ -z "${SHOSAI_DOWNLOAD_RU_ORIGIN:-}" ] || [ -z "${SHOSAI_DOWNLOAD_EU_ORIGIN:-}" ]; then
  rm -f "${NGINX_ENVSUBST_OUTPUT_DIR:?}/shosai/downloads.conf"
fi
