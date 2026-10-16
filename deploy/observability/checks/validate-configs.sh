#!/bin/sh
# Проверка конфигурации стека наблюдаемости (F5, задача CI «Observability»): каждый компонент
# проверяет свой файл сам, правила Prometheus проверяет и тестирует promtool, правила Loki — сам Loki:
# у него нет команды проверки правил, поэтому он запускается с ними и отвечает, сколько загрузил.
#
#   deploy/observability/checks/validate-configs.sh     # из корня репозитория, нужен Docker
set -eu

root=$(cd "$(dirname "$0")/.." && pwd)

collector=otel/opentelemetry-collector-contrib:0.162.0
loki=grafana/loki:3.7.8
tempo=grafana/tempo:3.1.0
prometheus=prom/prometheus:v3.15.0
blackbox=prom/blackbox-exporter:v0.28.0

echo "== коллектор"
docker run --rm -e SHOSAI_LOG_PROJECTS='^check$' --tmpfs /var/lib/otelcol/file_storage \
  -v "$root/collector/config.yaml:/etc/otelcol/config.yaml:ro" \
  "$collector" validate --config=/etc/otelcol/config.yaml

echo "== Loki"
docker run --rm -v "$root/loki/loki.yaml:/etc/loki/loki.yaml:ro" \
  "$loki" -config.file=/etc/loki/loki.yaml -verify-config

echo "== Tempo"
docker run --rm -v "$root/tempo/tempo.yaml:/etc/tempo/tempo.yaml:ro" \
  "$tempo" -config.file=/etc/tempo/tempo.yaml -config.verify=true

echo "== blackbox"
docker run --rm --user 65534:65534 -v "$root/blackbox/blackbox.yml:/etc/blackbox/blackbox.yml:ro" \
  "$blackbox" --config.file=/etc/blackbox/blackbox.yml --config.check

echo "== Prometheus: конфигурация, правила, тесты правил"
docker run --rm -e SHOSAI_ENVIRONMENT=check -v "$root/prometheus:/etc/prometheus:ro" \
  --entrypoint promtool "$prometheus" check config /etc/prometheus/prometheus.yml
docker run --rm -v "$root/prometheus/rules:/rules:ro" -w /rules --entrypoint sh "$prometheus" -c \
  'promtool check rules *.yml generated/*.recording.json generated/*.alerts.json \
   && promtool test rules tests/*.yml generated/*.test.json'

echo "== Loki: правила ruler"
expected=$(grep -c '^ *- alert:' "$root"/loki/rules/*.yml | awk -F: '{ sum += $NF } END { print sum }')
name="shosai-loki-rules-check-$$"
docker run -d --name "$name" --tmpfs /loki:uid=10001,gid=10001 --tmpfs /tmp \
  -v "$root/loki/loki.yaml:/etc/loki/loki.yaml:ro" -v "$root/loki/rules:/etc/loki/rules/fake:ro" \
  "$loki" -config.file=/etc/loki/loki.yaml >/dev/null
trap 'docker rm -f "$name" >/dev/null 2>&1 || true' EXIT
loaded=0
for _ in $(seq 1 60); do
  loaded=$(docker run --rm --network "container:$name" --entrypoint wget "$prometheus" -qO- \
    http://127.0.0.1:3100/loki/api/v1/rules 2>/dev/null | grep -c '^ *- alert:' || true)
  [ "$loaded" -ge "$expected" ] && break
  sleep 2
done
if [ "$loaded" -ne "$expected" ]; then
  echo "Loki загрузил правил: $loaded из $expected"
  docker logs "$name" 2>&1 | grep -iE 'rule|error' | tail -20
  exit 1
fi
echo "Loki загрузил правил: $loaded из $expected"
echo "конфигурация стека в порядке"
