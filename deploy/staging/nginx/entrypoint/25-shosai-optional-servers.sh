#!/bin/sh
# Необязательные серверы edge: блок Grafana — только при заданном SHOSAI_GRAFANA_SERVER_NAME
# (staging); иначе подставленный файл удаляется до старта NGINX. Запускается после подстановки
# шаблонов (20-envsubst-on-templates.sh образа).
set -eu
if [ -z "${SHOSAI_GRAFANA_SERVER_NAME:-}" ]; then
  rm -f "${NGINX_ENVSUBST_OUTPUT_DIR:?}/conf.d/grafana.conf"
fi
