# Observability stack

The stack of target architecture §16, built step by step by [F5](../../docs/plan/packages/F5-observability.md). One definition serves the local environment (with [compose.local.yaml](compose.local.yaml), see [docs/development.md](../../docs/development.md), "Observability") and staging (step 10 of the plan).

| Service | Image | Role |
|---|---|---|
| `collector` | `otel/opentelemetry-collector-contrib:0.162.0` | Reads container logs, receives OTLP traces, tail-samples, ships to Loki and Tempo through bounded queues |
| `loki` | `grafana/loki:3.7.8` | Logs, 14 days; labels `service`, `role`, `level`, `home` only |
| `tempo` | `grafana/tempo:3.1.0` | Traces, 7 days |
| `telemetry-volumes` | `busybox:1.37.0` | Runs once: gives the Loki and Tempo volumes to uid 10001 (their images have no shell) |

## Logs

- A container is shipped when its json-file log options carry `labels: "com.docker.compose.project,com.docker.compose.service"` and its project matches `SHOSAI_LOG_PROJECTS`. The collector reads `/var/lib/docker/containers` read-only as root with only `DAC_READ_SEARCH`; the Docker socket is not mounted. Offsets live in the `collector-storage` volume, so a restart ships nothing twice.
- `service` is the Compose service (`api`, `workers-critical`, `tempo`…). For a backend JSON line the collector adds `role`, `level` and `home` from the line; those four are the only Loki labels, and Loki refuses a fifth (`max_label_names_per_series: 4`).
- `trace_id`, `span_id`, `request_id`, `user_id`, `org_id`, `session_id`, `task_id`, `event_id` go to structured metadata. The body is the line exactly as the process wrote it.
- Query by an id inside a time range: `{service="api"} | request_id="…"`.

## Traces

Kept: every trace with an error, every trace with an HTTP server span slower than 300 ms, 5% of the rest. A trace's spans wait 10 s for the decision; late spans follow it.

## Limits and loss

- `memory_limiter` refuses data before the collector reaches 80% of its memory limit.
- Each exporter has a queue of 20 000 records or spans and retries for 60 s; a full queue or an expired retry drops the data. Every loss is counted on the collector's `:8888/metrics`: `otelcol_exporter_enqueue_failed_*` (queue full), `otelcol_exporter_send_failed_*` (retries expired), `otelcol_receiver_refused_*` (memory limit), `otelcol_processor_tail_sampling_sampling_trace_dropped_too_early` (more traces in flight than `num_traces`). The exporter counters appear once they are non-zero. No process ever waits on telemetry.

## Variables

| Variable | Default | Purpose |
|---|---|---|
| `SHOSAI_TELEMETRY_NETWORK` | `shosai-staging_plane` | The existing network the stack joins; locally `compose.local.yaml` sets `shosai-local_default` |
| `SHOSAI_LOG_PROJECTS` | `^shosai-staging$` | Regular expression of the Compose projects whose containers are shipped; locally `^shosai-local(-[a-z]+)?$` |

## Checking a config

```bash
docker run --rm -e SHOSAI_LOG_PROJECTS='^x$' --tmpfs /var/lib/otelcol/file_storage \
  -v $PWD/collector/config.yaml:/etc/otelcol/config.yaml:ro \
  otel/opentelemetry-collector-contrib:0.162.0 validate --config=/etc/otelcol/config.yaml
docker run --rm -v $PWD/loki/loki.yaml:/etc/loki/loki.yaml:ro grafana/loki:3.7.8 -config.file=/etc/loki/loki.yaml -verify-config
docker run --rm -v $PWD/tempo/tempo.yaml:/etc/tempo/tempo.yaml:ro grafana/tempo:3.1.0 -config.file=/etc/tempo/tempo.yaml -config.verify=true
```

## Known noise

Tempo 3.1 in single-binary mode logs `error calling scheduler … no jobs found` at `error` level whenever its background worker finds nothing to do, backing off up to once a minute. Nothing is lost; log-based rules (step 5) must not count these lines.
