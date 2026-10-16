# Образ конфигурации стека наблюдаемости (F5-D6): только файлы, ни одного процесса. CI собирает его
# из каждого коммита вместе с образами бэкенда и edge; на staging службы стека монтируют из него свои
# конфигурации, правила и дашборды (type: image, compose.staging.yaml), поэтому правила всегда
# совпадают с метриками кода, который работает, а откат возвращает и то и другое.
FROM scratch
COPY --link alertmanager/ /alertmanager/
COPY --link blackbox/ /blackbox/
COPY --link collector/ /collector/
COPY --link grafana/provisioning/ /grafana/provisioning/
COPY --link grafana/dashboards/generated/ /grafana/dashboards/generated/
COPY --link loki/ /loki/
COPY --link prometheus/prometheus.yml /prometheus/prometheus.yml
COPY --link prometheus/rules/ /prometheus/rules/
COPY --link tempo/ /tempo/
