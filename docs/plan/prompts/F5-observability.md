# F5 — Observability

Follow the common protocol in `docs/plan/prompts/README.md`. Load the skills `observability`, `distributed-logging`, `docker-compose-patterns` and `docker-destructive-guardrails` before starting; load `fastapi` before touching `backend/`.

## Goal

The observability stack of target architecture §16 running next to staging, so every slice ships with its metrics, logs, traces, SLOs and invariant monitors from the start.

## Read first

- Target architecture §16 in full, §14 rule 13, §18.2 (versions).
- The draft's `deploy/prometheus`, `deploy/alertmanager`, `deploy/blackbox` and `features/alerting`, for lessons only.

## Work

1. OpenTelemetry Collector: logs from container stdout and OTLP traces; tail sampling (100% errors and slow requests, 5% of the rest); bounded buffer that drops and counts on overflow.
2. Prometheus with retention and size caps; exporters (node, nginx, blackbox); uptime probes from outside the plane.
3. Loki and Tempo as single binaries with the retention and caps of §16.7; label discipline exactly as §16.7.
4. Grafana with the three data sources linked (exemplars, trace to logs, log to trace).
5. Alertmanager to Telegram; paging only on SLO burn and invariant monitors (§16.3, §16.4); tickets for the rest (§16.6).
6. Dashboards per journey, per process role, per home and per AI provider (§16.5), as code.
7. The backend `alerting` domain from the draft, rewritten per v2 rules.
8. A guide in `docs/observability.md` for slices: how to add a metric, a span, an SLO and an invariant monitor.

## Definition of done

- Staging telemetry appears in Grafana: one request is traceable from NGINX through the API to the database, with its logs.
- A test alert reaches Telegram.
- No personal data, meeting text or tokens appear in labels, spans or logs (§16.8), checked by a test.
