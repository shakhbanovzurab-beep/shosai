#!/bin/sh
# Корень образа только для чтения: шаблоны подставляются в tmpfs /tmp (NGINX_ENVSUBST_OUTPUT_DIR).
set -eu
mkdir -p "${NGINX_ENVSUBST_OUTPUT_DIR:?}"
