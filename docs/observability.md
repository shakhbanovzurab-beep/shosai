# Observability for a slice

How a slice of the backend becomes observable: logs, metrics, spans, objectives, invariant monitors, dashboards, runbook entries, business alerts and the debug switch. The stack itself — collector, Loki, Tempo, Prometheus, Grafana, Alertmanager — is described in [deploy/observability/README.md](../deploy/observability/README.md); the rules behind it are [target architecture](design/ARCHITECTURE.md) §16 and the [F5 plan](plan/packages/F5-observability.md).

## What a slice gets without writing anything

- **Logs.** Every line is one JSON object with `role`, `service`, `level`, a timestamp and, inside a span, `trace_id` and `span_id`. A request's lines carry `request_id` and, once the caller is known, `user_id`, `org_id` and `home`. A task run's lines carry `task_name`, `task_id` and the ids of its payload; an event delivery's carry `event_id`.
- **HTTP.** `http_server_request_duration_seconds` by route template, method, status class, error type and the caller's `home`, with a `trace_id` exemplar on every 5xx and on every request slower than 300 ms; one INFO line per request.
- **Spans.** The edge opens the root span; the API, every database transaction, task, event delivery, S3 call and AI call add theirs. The collector keeps every trace with an error or a slow HTTP span and 5% of the rest.
- **Platform metrics.** Tasks, queues, the outbox, database pools, Valkey, AI calls and their cost, event-loop lag.

A slice adds telemetry only for what is specific to it.

## Privacy first (§16.8)

Only ids go into logs, span attributes and metric labels: never an email, a name, a phone number, an address, a meeting's or a document's text, a prompt, a password, a code or a token. The collector masks values shaped like an email, a JWT, a bearer token or a URL password as a second line of defence; it is not a licence.

A slice whose flows handle personal data adds a canary test like [tests/features/identity/test_telemetry_privacy.py](../backend/tests/features/identity/test_telemetry_privacy.py): it drives the flows with canary values and asserts with `tests/core/observability/telemetry_canaries.py` that none reaches a log line, a span or a metric label.

## Logs

```python
import structlog

log = structlog.stdlib.get_logger(__name__)

log.info("Встреча записана", meeting_id=str(meeting_id), duration_s=duration)
```

- The message is Russian, for the engineer; keys are English identifiers. Ids are logged as text (`str(uuid)`, or `id_fields(user_id=…, org_id=…)` from `core/observability/log_context.py`, which skips the unknown ones).
- Levels: `info` for what happened, `warning` for a failure the code handled, `error` for one it could not, `exception` inside `except` to keep the stack. Never `print()`.
- `debug` for detail useful when following one person's problem: what was decided and with which numbers. DEBUG lines are not written unless the debug switch is on for that person or company (below).
- Ids a unit of work already carries need not be repeated: `log_context(...)` and `bind_log_fields(...)` bind them for every line of the block or task.

## Metrics

One class per slice part, built with the process's registry from `CoreServices.registry`:

```python
from typing import Literal

from prometheus_client import CollectorRegistry, Counter


class MeetingMetrics:
    """Recorded meetings by outcome."""

    def __init__(self, registry: CollectorRegistry) -> None:
        self._recorded = Counter(
            "shosai_notes_recorded",
            "Записанные встречи по исходу",
            ("outcome",),
            registry=registry,
        )

    def recorded(self, outcome: Literal["saved", "failed"]) -> None:
        """One meeting recorded."""
        self._recorded.labels(outcome=outcome).inc()
```

- Name: `shosai_<slice>_<what>`, with the unit as a suffix where one applies (`_seconds`, `_bytes`); a counter gets `_total` from the client.
- Labels come from closed sets declared in code: an outcome, a provider, a queue, a home. Never an id, a free text or anything a user chooses (§16.7).
- Never the label names `job`, `instance`, `role` or `service`: Prometheus sets them on every target and would rename the slice's label `exported_*`. The catalog test refuses them.
- A metric that a rule or a dashboard names must be exported by some role: the catalog test in `tests/composition/test_observability_rules.py` starts the roles and checks.

## Spans

Most work already runs inside a span. Open one for a step worth seeing on its own in a trace — a call to an external service the platform does not wrap, a long computation:

```python
tracer = services.tracer_provider.get_tracer(__name__)

with tracer.start_as_current_span("meetings.transcode", attributes={"meeting.format": fmt}):
    ...
```

- Attributes follow the rule of logs: ids, closed sets, numbers. A failure ends the span with an error status, set by the context manager when the exception leaves it.
- An outbound HTTP call to a third party through a slice's own `httpx` client is not traced automatically; open a span around it.

## An objective (SLO, §16.3)

A slice declares the promises it makes to people on its `FeatureModule`:

```python
from shosai.core.observability.objectives import EventRatio, Journey, ServiceLevelObjective

MEETING_JOURNEY = Journey("meetings", "Встречи")

MEETING_OBJECTIVES = (
    ServiceLevelObjective(
        name="meeting_start_availability",
        journey=MEETING_JOURNEY,
        summary="Встречи не начинаются: запуск заканчивается ошибкой",
        promise="встреча начинается без ошибки с нашей стороны в 99,5 % случаев",
        target=0.995,
        indicator=EventRatio(
            total='http_server_request_duration_seconds_count{http_route="/v1/notes"}',
            bad='http_server_request_duration_seconds_count{http_route="/v1/notes",error_type!=""}',
        ),
    ),
)

MEETINGS = FeatureModule(name="meetings", ..., objectives=MEETING_OBJECTIVES)
```

- `summary` is what people experience, `promise` completes «Мы обещаем, что …»: both are plain Russian for the owner, without terms. They become the alert's message and the dashboard's heading.
- `EventRatio` counts bad events among all; `LatencyRatio(histogram, matchers, threshold)` counts events slower than a histogram bucket — the threshold must be one of the histogram's buckets.
- `alerting=AlertClass.TICKET` tracks the promise without waking anyone, as for the Russian home's latency. A burn whose threshold (its factor × the error budget) is 1 or more cannot fire and is not rendered: an objective of 80 % keeps only the 3-day ticket.
- Then, in `backend/`: `uv run --env-file ../.env.example pytest tests/composition/test_observability_rules.py --update-rules`. It renders the recording rules, the multi-window burn-rate alerts, their promtool tests and the journey's dashboard into `deploy/observability/`; commit them with the code. The same test fails while they differ from the declarations.

## An invariant monitor (§16.4)

A rule that must never break, watched by a metric that stays at zero while it holds:

```python
from shosai.core.observability.objectives import InvariantMonitor, StaysAtMost

MEETING_MONITORS = (
    InvariantMonitor(
        name="recording_without_owner",
        invariant="inv-12",
        summary="Есть запись встречи без владельца",
        explanation="Запись должна принадлежать встрече: без владельца её нельзя ни показать, ни удалить.",
        condition=StaysAtMost("shosai_notes_orphan_recordings"),
    ),
)
```

- `NeverIncreases(counter, window)` for a counter of violations, `StaysAtMost(gauge, limit)` for a gauge a periodic check sets.
- A monitor pages. `summary` says what broke, `explanation` what it threatens, both in plain Russian.
- It gets a tile on the dashboard «Правила, которые не должны нарушаться» and needs a runbook section with the anchor of its name with dashes (`recording-without-owner`).

## A dashboard panel

- A journey's dashboard is generated from its objectives: a slice that declares an SLO gets its panels.
- A latency to show with no promise and no alert — measured and reported, not paged — is a `TrackedLatency(journey, title, description, histogram, series)` in the slice's `tracked`: a chart of the time 95 % of events stay under, one line per `(label, matchers)`, after the journey's promises (Leo's turn tracks the platform's time of both homes and the worker's pickup, agent step 17).
- The other dashboards are code in `backend/src/shosai/composition/dashboards.py` and `ai_dashboard.py`, built from `core/observability/grafana.py` (charts) and `tiles.py` (single numbers). A panel is a `Chart(title, description, unit, series, limit=…)`, at most four `Series` each, or a `status`/`share`/`Tile`.
- Everything the owner reads on a panel is plain Russian: title, description, legend, unit. `--update-rules` renders the dashboards with the rules; Grafana picks the files up within a minute.

## A runbook entry

Every alert links to a section of [docs/runbooks/alerts.md](runbooks/alerts.md): `<a id="anchor"></a>`, then **Means**, **Look** and **Fix**. `deploy/observability/checks/validate-configs.sh` (CI job "Observability") fails when a rule names an anchor the runbook lacks; the `alerting` slice's tests check its kinds.

## A business alert

A business event the owner should hear about — not a failure — is a kind of the `alerting` slice ([ADR 0052](adr/0052-business-events-to-the-monitoring-chat-through-alertmanager.md)): a builder of its texts, a subscription and a runbook section, described in [its README](../backend/src/shosai/features/alerting/README.md). The alert carries ids, amounts and the admin card's link, never a person's details.

## The debug switch (§16.7)

Logs are INFO. To follow one person's or one company's problem, an operator turns DEBUG on for them for up to an hour:

```bash
shosai observability debug --user <id> --minutes 30 --reason "Ticket 42: sign-in fails"
shosai observability debug --org <id> --minutes 15 --reason "…"
shosai observability debug                       # the switches that are on
shosai observability debug --user <id> --off
```

On staging: `sudo -u deploy docker compose exec api shosai observability debug …` in `/srv/shosai`.

- Every process reads the switches from Valkey every 15 s and logs «Отладочные журналы включены» and «… выключены».
- While a switch is on, Shosai's own loggers write DEBUG lines and only the lines of that user or company pass; the libraries' loggers stay at INFO, since their debug lines carry SQL parameters and headers. A line written after the switch ended does not pass, even before the next read.
- In Grafana: Explore → Loki, `{level="debug"} | user_id="<id>"`.
- The platform writes DEBUG lines for each committed transaction (home, mode, duration), each task queued, each event written and each paid model call (provider, model, tokens, cost).

## Before finishing a slice

- No personal data in any new log line, attribute or label; a canary test for flows with personal data.
- New metrics have closed label sets and none of the four reserved names.
- Objectives and monitors declared on the `FeatureModule`, rules and dashboards rendered with `--update-rules` and committed, a runbook section per alert.
- `deploy/observability/checks/validate-configs.sh` passes.
- A slice with shareable resources follows [access.md](access.md): its tables are covered by workspaces' inv-14 self-test only when the sweep role may read them.
