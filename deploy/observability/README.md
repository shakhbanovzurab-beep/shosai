# Observability stack

The stack of target architecture §16, built step by step by [F5](../../docs/plan/packages/F5-observability.md). One definition serves the local environment (with [compose.local.yaml](compose.local.yaml), see [docs/development.md](../../docs/development.md), "Observability") and staging (step 10 of the plan).

| Service | Image | Role |
|---|---|---|
| `collector` | `otel/opentelemetry-collector-contrib:0.162.0` | Reads container logs, receives OTLP traces, tail-samples, ships to Loki and Tempo through bounded queues |
| `loki` | `grafana/loki:3.7.8` | Logs, 14 days; labels `service`, `role`, `level`, `home` only |
| `tempo` | `grafana/tempo:3.1.0` | Traces, 7 days |
| `prometheus` | `prom/prometheus:v3.15.0` | Metrics, 30 days or `PROMETHEUS_RETENTION_SIZE`, whichever ends first; exemplar storage on |
| `node-exporter` | `prom/node-exporter:v1.12.1` | The host's disks, memory and CPU; the host's root read-only at `/host` |
| `nginx-exporter` | `nginx/nginx-prometheus-exporter:1.5.3` | The edge's connections from `stub_status` on its internal port 8082 |
| `grafana` | `grafana/grafana:13.2.4` | One pane with the three data sources linked; one admin, no sign-up, no anonymous access, its own alerting off |
| `blackbox` | `prom/blackbox-exporter:v0.28.0` | Probes from inside the plane: health through the edge with its certificate's expiry, TCP to each home's database |
| `telemetry-volumes` | `busybox:1.37.0` | Runs once: gives the Loki and Tempo volumes to uid 10001 (their images have no shell) |

## Logs

- A container is shipped when its json-file log options carry `labels: "com.docker.compose.project,com.docker.compose.service"` and its project matches `SHOSAI_LOG_PROJECTS`. The collector reads `/var/lib/docker/containers` read-only as root with only `DAC_READ_SEARCH`; the Docker socket is not mounted. Offsets live in the `collector-storage` volume, so a restart ships nothing twice.
- `service` is the Compose service (`api`, `workers-critical`, `tempo`…). For a backend JSON line the collector adds `role`, `level` and `home` from the line; those four are the only Loki labels, and Loki refuses a fifth (`max_label_names_per_series: 4`).
- `trace_id`, `span_id`, `request_id`, `user_id`, `org_id`, `session_id`, `task_id`, `event_id` go to structured metadata. The body is the line exactly as the process wrote it.
- Query by an id inside a time range: `{service="api"} | request_id="…"`.

## Traces

- The edge opens the root span of every request to `/v1/`, `/v1/ws/` and `/email/` (`ngx_otel_module` of the `-otel` NGINX image) with `otel_trace_context inject`: a client's `traceparent` is overwritten, so no caller chooses our trace ids or sampling. Tracing is on where a collector runs next to the edge: `SHOSAI_OTEL_TRACE=on` (the image's default is `off`, because without a collector the module logs an export error every 5 s); the address is `SHOSAI_OTEL_ENDPOINT` (`collector:4317`). A collector the edge cannot reach does not stop it from starting or serving; its spans are dropped.
- The collector deletes span attributes that may carry a person's input — client address and port, user agent, raw URL, path and query — whatever service sent them; the backend never writes them, the edge does by default.
- Kept: every trace with an error, every trace with an HTTP server span slower than 300 ms, 5% of the rest. A trace's spans wait 10 s for the decision; late spans follow it. The threshold is the backend's `SLOW_REQUEST_SECONDS` too: they change together.

## Grafana

- Data sources are provisioned read-only from [grafana/provisioning/datasources](grafana/provisioning/datasources/datasources.yaml): Prometheus (default), Loki, Tempo.
- **Metric → trace:** the backend's HTTP histogram carries `trace_id` exemplars on server errors and requests slower than 300 ms — exactly the traces the collector keeps; Prometheus stores them (`exemplar-storage`) and Grafana opens them in Tempo.
- **Trace → logs:** a span's "Related logs" runs `{service=~".+"} | trace_id="…"` over the trace's time range ± 5 min.
- **Log → trace:** `trace_id` in a line's structured metadata is a link to the trace.
- The admin's password comes from the file `admin-password` in `GRAFANA_SECRETS_DIR` (staging); locally it is `local-grafana` unless `LOCAL_GRAFANA_PASSWORD` says otherwise. `GOMEMLIMIT` keeps Grafana's heap under its 384 MB limit: at 192 MB Grafana 13 was killed for memory as soon as its UI was used.

## The edge's log

One JSON line per request without personal data: no client address, no user agent, no path or query — a 404's path is whatever the client typed. It carries the request id, the trace id (traced locations only), the method, the path's class by its first segment (`/v1`, `/app`, `/admin`, `/email`, `/`, `other`), the status, sizes and times, and `level` from the status. The API's line with the same `request_id` and `trace_id` has the route template. NGINX's own `error_log` lines are text with the client's address and the raw request; the collector replaces `client`, `request`, `upstream` and `referrer` in them with `<hidden>`.

## Limits and loss

- `memory_limiter` refuses data before the collector reaches 80% of its memory limit.
- Each exporter has a queue of 20 000 records or spans and retries for 60 s; a full queue or an expired retry drops the data. Every loss is counted on the collector's `:8888/metrics`: `otelcol_exporter_enqueue_failed_*` (queue full), `otelcol_exporter_send_failed_*` (retries expired), `otelcol_receiver_refused_*` (memory limit), `otelcol_processor_tail_sampling_sampling_trace_dropped_too_early` (more traces in flight than `num_traces`). The exporter counters appear once they are non-zero. No process ever waits on telemetry.

## Privacy (§16.8)

No personal data, meeting text, secret or client trace reaches a label, a span or a log line. Three layers keep it so:

1. **Sources.** The backend logs ids only (`LogFields`), redacts secrets by key and inside URLs, drops the request's private span attributes before a span exists, and keeps metric labels in closed sets. The edge logs no address, agent, path or query.
2. **Collector.** It deletes span attributes that carry a client's address, agent or raw URL, hides `client`, `request`, `upstream` and `referrer` in NGINX's text error lines, and — the last line — masks anything shaped like an email address, a JWT, a bearer token or a password inside a URL in log lines, log attributes, span names, span attributes and span events (`<email>`, `<jwt>`, `Bearer <token>`, `://<credentials>@`). Operators' own queries logged by Loki and Tempo are masked the same way.
3. **Checks.**
   - `backend/tests/features/identity/test_telemetry_privacy.py` runs identity's flows — registration with its mailed code, sign-in, the token on `/v1/auth/me`, a new name, failed sign-ins, a reset request, a stranger's path and query, from a canary client address and agent — through the real logging pipeline at DEBUG, every span of the app, both homes and Valkey without sampling, and every metric registry; no canary may appear. `tests/core/observability/telemetry_canaries.py` is the search every slice reuses for its own flows.
   - [checks/privacy-canary.sh](checks/privacy-canary.sh) does the same end to end: requests that store nothing go through the edge with canaries, then the canaries are searched in Loki, in every trace of the window in Tempo, and in every series and exemplar of Prometheus. It fails when it finds one, and when the requests' own lines are missing from Loki or, for a sign-in slower than the sampling threshold, its trace from Tempo.

   Both were checked once with a leak planted on purpose — a log line and a span attribute — and failed as they should.

## Metrics

- Each backend role is found by Docker DNS on its Compose service name at `:9100` (`OPS_PORT`): while a release hands over, both containers behind a name are scraped. `job` and `role` name the role; workers carry `queue` from the service name. `instance` is the container's address and changes with each release.
- A role that is not running has no target at all, so no `up` series exists for it and Prometheus logs a DNS error every 15 s: rules (step 5) watch roles with `absent()` as well as `up == 0`.
- Probe targets live in a directory of `file_sd` files: locally [prometheus/targets/local](prometheus/targets/local); on staging the files are rendered on the host, because they name the managed databases (`SHOSAI_PROBE_TARGETS_DIR`). Each target names its blackbox `module` and a `probe` label (`edge_health`, `home_database` with `home`).
- The node exporter runs in the stack's network, so its network counters would describe the container only: those collectors are off. Disks, memory, CPU and load describe the host.
- The external label `environment` comes from `SHOSAI_ENVIRONMENT`. Prometheus re-reads its configuration on `SIGHUP` (`docker compose kill -s HUP prometheus`); its lifecycle HTTP API stays off, so nothing on the network can stop it.

## Variables

| Variable | Default | Purpose |
|---|---|---|
| `SHOSAI_TELEMETRY_NETWORK` | `shosai-staging_plane` | The existing network the stack joins; locally `compose.local.yaml` sets `shosai-local_default` |
| `SHOSAI_LOG_PROJECTS` | `^shosai-staging$` | Regular expression of the Compose projects whose containers are shipped; locally `^shosai-local(-[a-z]+)?$` |
| `SHOSAI_ENVIRONMENT` | `staging` | The `environment` external label of every series and alert; locally `local` |
| `PROMETHEUS_RETENTION_SIZE` | `5GB` | Prometheus's size cap (F5-D3); the time limit is 30 days |
| `GRAFANA_ROOT_URL` | `https://grafana.shosai.tech` | Grafana's public address, for its links (F5-D1); locally `http://127.0.0.1:3000` |
| `GRAFANA_ADMIN_USER` | `admin` | The one Grafana admin's login |
| `GRAFANA_SECRETS_DIR` | `/srv/shosai/secrets/grafana` | Host directory with the file `admin-password`, readable by Grafana's uid 472; locally a tmpfs replaces it |
| `SHOSAI_PROBE_TARGETS_DIR` | `/srv/shosai/telemetry/probe-targets` | Host directory of the probe target files; locally `compose.local.yaml` mounts `prometheus/targets/local` |

## Checking a config

```bash
docker run --rm -e SHOSAI_LOG_PROJECTS='^x$' --tmpfs /var/lib/otelcol/file_storage \
  -v $PWD/collector/config.yaml:/etc/otelcol/config.yaml:ro \
  otel/opentelemetry-collector-contrib:0.162.0 validate --config=/etc/otelcol/config.yaml
docker run --rm -v $PWD/loki/loki.yaml:/etc/loki/loki.yaml:ro grafana/loki:3.7.8 -config.file=/etc/loki/loki.yaml -verify-config
docker run --rm -v $PWD/tempo/tempo.yaml:/etc/tempo/tempo.yaml:ro grafana/tempo:3.1.0 -config.file=/etc/tempo/tempo.yaml -config.verify=true
docker run --rm -e SHOSAI_ENVIRONMENT=local -v $PWD/prometheus:/etc/prometheus:ro --entrypoint promtool \
  prom/prometheus:v3.15.0 check config /etc/prometheus/prometheus.yml
docker run --rm --user 65534:65534 -v $PWD/blackbox/blackbox.yml:/etc/blackbox/blackbox.yml:ro \
  prom/blackbox-exporter:v0.28.0 --config.file=/etc/blackbox/blackbox.yml --config.check
```

## Known noise

Tempo 3.1 in single-binary mode logs `error calling scheduler … no jobs found` at `error` level whenever its background worker finds nothing to do, backing off up to once a minute. Nothing is lost; log-based rules (step 5) must not count these lines.
