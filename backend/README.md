# Shosai backend

One modular monolith, one image, four process roles (`api`, `ws`, `workers`, `scheduler`), built feature-first: `core/`, `features/<slice>/`, `composition/`, `entrypoints/` under `src/shosai/` ([target architecture](../docs/design/ARCHITECTURE.md) §5). [F1](../docs/plan/packages/F1-backend-foundation.md) built the foundation described here; each slice adds its own README in its package.

## Boundaries

import-linter contracts in `pyproject.toml` (`uv run lint-imports`):

| Contract | Rule |
|---|---|
| Layers | `entrypoints` → `composition` → `features` → `core`; never upward |
| Features meet through contracts | a slice imports another slice only through its `contracts` module |
| Pure kernel | `core.kernel` imports no framework, driver, client or telemetry library |
| Pure slice domain | `features.<slice>.domain` imports, directly or through another module, no framework, driver, client, telemetry library, agent runtime (LangGraph) or AI provider SDK |

## Configuration

`core/config` reads the settings once per process from environment variables and passes them in; nothing reads a `.env` file or keeps a cached global. Every variable is documented with its purpose in section 2 of [`.env.example`](../.env.example), and a test keeps that section in step with the settings sections. Locally uv passes the file: `uv run --env-file ../.env …`.

- `load_settings(os.environ)` reports every invalid or missing variable at once, by name, never by value.
- `ENVIRONMENT` is required. With `staging` or `production` — every environment but `development` (F1 audit OD-7) — `enforce_production_gate` refuses to start, naming the setting, when the API docs are on, `TRUSTED_PROXY_ADDRESSES` or `FERNET_KEY` is missing, `LOG_LEVEL` is `DEBUG`, the bucket's endpoint is not `https`, `VALKEY_URL` is neither `rediss://` nor `redis://` at a private-network IP address (ADR 0042) or a home's database address lacks `sslmode=verify-full`. A slice adds its own checks through `extra_checks`.
- A slice declares its own section as a subclass of `SettingsSection` and documents its variables in section 2.

## Logs, traces, metrics

`core/observability` follows target architecture §16.

- Log with `structlog.stdlib.get_logger(__name__)`: the message in Russian, fields as English keyword arguments. Standard-library loggers go through the same renderer: one JSON line per event on stdout with `timestamp`, `level`, `logger`, `role`, `service`, and inside a span `trace_id` and `span_id`.
- `log_context(request_id=…, home=…, org_id=…, user_id=…, session_id=…, task_name=…, task_id=…)` adds the ids of a unit of work to every line inside the block.
- Values under sensitive keys, `SecretStr` values and passwords inside URLs are replaced by `***`; never log request bodies, headers, query strings, personal data or meeting text.
- Lines and spans leave through bounded queues and never block the event loop; what does not fit is dropped and counted in `shosai_telemetry_dropped_total{signal, reason}`. Without `OTEL_EXPORTER_OTLP_ENDPOINT` spans are recorded for the log correlation but not exported.
- Metrics register in the process registry passed in (`build_metrics_registry`), never in the global one; labels stay bounded (§16.7). `watch_event_loop_lag` feeds `shosai_event_loop_lag_seconds`.

## HTTP shell

`core/web` builds every public app: `build_http_app(web_settings, HttpTelemetry(registry, tracer_provider), routers)`. Nothing creates an app at import time; a role builds its app at start.

- **Middlewares**, outermost first: `RequestBoundary` — the request id of [ADR 0008](../docs/adr/0008-error-envelope-with-compatible-detail.md), the log context, `X-Request-ID`, `X-Content-Type-Options`, `Referrer-Policy` and, over HTTPS, `Strict-Transport-Security` on every response, one access line (`method`, `route` template, `status`, `duration_ms`), the HTTP metrics and the last-resort 500; then CORS, only for `CORS_ALLOWED_ORIGINS`. Both are pure ASGI.
- **HTTP metrics** ([ADR 0012](../docs/adr/0012-http-metrics-in-the-request-boundary.md)): the boundary records each request once, from the same outcome as the access line, into one histogram under the OpenTelemetry semantic conventions for HTTP servers, as the SDK's Prometheus exporter names it: `http_server_request_duration_seconds{http_request_method, http_route, http_response_status_code, url_scheme, error_type}` with the conventions' advisory buckets; name, help text, labels and buckets are pinned by `tests/core/web/test_http_metrics.py`. Rate and errors come from its count. Label values come from closed sets: `http_route` is a served route template or empty, `http_request_method` a known method or `_OTHER`, `http_response_status_code` the code the application sent (empty when no response started), `url_scheme` `https` or `http`, `error_type` the code of a 5xx, `_OTHER` without a response, else empty; a raw path, a query or a client's method never becomes a label.
- **Route templates:** `RouteTemplates` reads the template from what FastAPI's routing left in the scope, through maps built at start; nothing matches the path a second time. `include_router(prefix=…)`, nested routers, mounts and plain Starlette routes are supported. The app refuses to start when one router instance is included twice (build it twice by its factory instead) or when it meets a kind of route `RouteTemplates` does not know.
- **Traces:** FastAPI's native tracing wraps the stack — one server span per request, named by the route template, no spans for dependencies and serialization. The process sampler drops raw paths, queries, full URLs, client addresses and user agents from every span (§16.8).
- **Errors:** a slice raises `AppError(code, HTTPStatus.…, params=…, detail=…)` from `core.kernel.errors` and never builds an error body. The code is snake_case (the client's i18n key `errors:<code>`); a text param is only a code or an id, so an email or a name cannot pass; `detail` is set only on a `native` route whose draft contract gives it another shape; a `retry_after_seconds` param becomes `Retry-After`. The handlers also render `HTTPException` (a code-like `detail` becomes the code, a sentence is replaced by the status code, headers such as `Allow` and `WWW-Authenticate` are kept), validation (422 with the `loc` and `type` of each field, never the input) and an unknown path (404 JSON). An unhandled exception is one 500 envelope and one error line with its stack.
- **OpenAPI:** the `default` response of every operation is `ErrorResponse`. The docs (`/docs`, `/redoc`, `/openapi.json`) exist only with `API_DOCS_ENABLED=true`, which the production gate refuses.
- **Proxy trust** is uvicorn's: `forwarded_allow_ips(web_settings)` lists `TRUSTED_PROXY_ADDRESSES`; an empty list trusts nobody, so `X-Forwarded-*` from anyone else is ignored.
- **Health:** `GET /v1/health` answers `200 {"status": "ok"}` with `Cache-Control: no-store` and checks no dependency. The cabinet's generated client calls it; it is not a native route, so the native-contract gate does not cover it.

## Data access

`core/db` gives every process exactly one connection pool per data home (§14 rule 2) and opens short transactions in the home of a tenancy scope (§4.1, §7). The driver is psycopg 3 without server-side prepared statements, behind PgBouncer in transaction mode ([ADR 0013](../docs/adr/0013-psycopg-driver-behind-pgbouncer.md)).

- **Engines:** `HomeDatabases.create(urls, role, tracer_provider=…)` builds one engine per home from the application-role addresses. Limits per role come from §4.3: pool 10 / 5 / 2 / 2 for `api` / `workers` / `ws` / `scheduler`, no overflow, pool wait 2 s, statement timeout 10 s (60 s for `workers`), recycle after 600 s, no pre-ping, TCP keepalives. Bound values never reach an exception text or a log.
- **Transactions:** a slice receives `HomeTransactions` and writes `async with transactions.begin(TenancyScope(home, user_id, org_id), read_only=…) as session:`. The first statement sets, for this transaction only, the statement timeout, read-only mode and `app.user_id` / `app.org_id`; the block commits on exit and rolls back on error. There is no request-wide session: commit before answering, and call external services between transactions, never inside one. A scoped read costs four round trips (`BEGIN`, scope, statement, `COMMIT`).
- **A home out of reach** answers 503 `home_unavailable` with `Retry-After`, for its users only (§13.2): an exhausted pool or a refused connection is counted in `shosai_db_unavailable_total{home, reason}`.
- **Home check:** `HomeGate.verify_at_start()` reads `home_identity` and the revision of each home. Another home's database or a schema behind the code stops the start; a newer schema (an image rolled back) passes with a warning; a home out of reach does not stop the start and is checked again before its first transaction ([ADR 0010](../docs/adr/0010-home-scoped-revisions-in-one-alembic-history.md), item 6). `shosai_db_home_state{home}` reports the result.
- **Models:** declare tables on `ModelBase` and list the model in `composition/metadata.py`. A table that exists only in the EU home declares `__table_args__ = {"info": table_info(homes=(Home.EU,))}`; code that reads it names `Home.EU` explicitly. Constraint names follow `NAMING_CONVENTION`.
- **Row-level security:** `app_user_id()` and `app_org_id()` read the scope of the transaction. `enable_company_isolation(table)` in a revision makes a table with `org_id` show a company's rows only within that company's scope.
- **Telemetry:** one client span per statement under the current span, with the parametrised SQL text, never the values; pool occupancy per home in `shosai_db_pool_connections{home, state}` and `shosai_db_pool_capacity{home}` (`register_pool_occupancy`).

## Migrations

- **Monthly partitions** (§8.2, `core/db/partitions`): a high-volume parent is created with `postgresql_partition_by=monthly_partition_range("created_at")` (the column in the primary key; the same option in the model's `__table_args__`) and registered with `register_monthly_partitions(MonthlyPartitions(table, ahead_months=2, keep_months=…))`, which creates the partitions due now; its downgrade calls `unregister_monthly_partitions(table)` before dropping it. Partitions are `<table>_pYYYYMM`, one per month in UTC, with no default partition. The tick `db.maintain_partitions` (daily, per home) runs `maintain_monthly_partitions(table)` for every registered table: a function owned by the migration role that creates partitions ahead (create, then `ATTACH`, which does not block reads or writes) and drops those past `keep_months`; a drop that cannot get its lock within 2 s waits for the next tick. The application role may call the function and read `partition_policies`, nothing more. `shosai_partition_coverage_seconds{home, table}` says how far ahead a table takes rows. The schema test and autogenerate skip partitions (`is_model_table`).

One Alembic history in `src/shosai/migrations/` for both homes, applied home by home by `core/db/migrations.py` under the migration role over a direct connection ([ADR 0010](../docs/adr/0010-home-scoped-revisions-in-one-alembic-history.md)).

- `uv run alembic revision -m "…"` writes a revision from the template. A revision declares `applies_to` (`EVERY_HOME` or a subset) and wraps `upgrade(scope)` and `downgrade(scope)` with `runs_in(applies_to)`; in another home the step is skipped and the revision is still stamped. A revision is either for every home or for one set, never both.
- Changes only expand the schema (§17), and every revision has a working downgrade: each test run executes it.
- New tables are closed to the application role until `grant_to_application(scope, table, privileges)`; `revoke_from_application` undoes it.
- A test compares the models with the migrated schema of each home (`compare_metadata` must be empty).

## Valkey, cache, object storage

Slices receive these clients from composition by injection; none is a global.

- **Clients:** `connect_redis(url, client_name, tracer_provider)` gives one client with a bounded pool (64 connections) per Redis-protocol server per process: Valkey (`VALKEY_URL`) and the LRU cache (`REDIS_CACHE_URL`). The client never retries by itself: every call waits at most its own deadline (`asyncio.timeout`), and the caller decides what a failure means. Commands become client spans with their arguments replaced by `?`. Keys are `shosai:<purpose>:<part>…` (`build_key`), parts from `[A-Za-z0-9_.-]`, so no free text becomes a key.
- **Locks:** `async with locks.hold(name, ttl=…, outage=LockOutagePolicy.FAIL_CLOSED) as lease:` — `lease` is None while another process holds the lock; extend long work with `await lease.extend(ttl)`, which is False once the lock was lost. Every caller states what happens when Valkey does not answer within 50 ms: fail closed raises `LockUnavailableError`, fail open runs the work unguarded. Release and extension compare the holder's token in Lua.
- **Rate limits** ([ADR 0011](../docs/adr/0011-rate-limits-gcra-in-valkey.md)): declare `RateLimit("sign_in", rate=5, period=timedelta(minutes=1), burst=5)` and put `Depends(rate_limited(limiter, limit))` on the route; the subject is the client address by default or any dependency returning a key, such as the user id; `detail=` keeps a native route's draft `detail`. Over the limit: 429 `rate_limited` with `Retry-After`. Valkey out or slower than 50 ms: the request passes, counted in `shosai_rate_limit_decisions_total{limit, decision="failed_open"}`.
- **Cache:** the port `Cache` (`get`, `get_many`, `set` with a TTL, `delete`), adapter `RedisCache`. Keys are `CacheKey(namespace, name)`; the namespace is a fixed code with the version of the value's shape (`directory.v1`). Every entry has a TTL, shortened by up to 10% at random; a call waits at most 20 ms; any failure is a miss, counted in `shosai_cache_operations_total{namespace, operation, result}`. Never cache access rights (§7).
- **Object storage** ([ADR 0014](../docs/adr/0014-one-object-store-in-russia.md), [ADR 0015](../docs/adr/0015-aiobotocore-instead-of-aioboto3.md)): the ports `ObjectStorage` and `MultipartUploads`, adapters `S3ObjectStorage` and `S3MultipartUploads` over one aiobotocore client of the one bucket (`open_s3_client(settings.storage)`): connect 2 s, read 20 s, at most 3 attempts. Clients upload and download with presigned requests valid 15 minutes; an upload link is signed for one content type and one length, a download link can pin the content type. The bucket out of reach is 503 `storage_unavailable` with `Retry-After`; a missing object is `ObjectNotFoundError`, a refused request `StorageRejectedError(code)`. Keys may contain file names, so they never enter logs, spans or metrics. No database transaction is open across a storage call (§14 rule 8).
- **Outages** of these dependencies are logged at most once per 10 s per operation (`OutageLog`), with the number of failures held back; every failure is counted.
- **Readiness:** `probe_dependencies([redis_probe("valkey", …), redis_probe("cache", …), storage_probe(objects)])` checks every dependency at once, each within 2 s, and reports `ok` or `down`; only the failures a probe declares mean `down`.

## Tasks

`core/tasks` is TaskIQ on Valkey streams with our own broker ([ADR 0016](../docs/adr/0016-own-task-broker-on-valkey-streams.md)): four queues by latency class — `critical` (money, email), `default`, `bulk`, `meeting` — one stream each, holding only unfinished tasks.

- **Declare** a task once, as a module constant of the slice: `TaskDeclaration(name="meetings.send_digest", queue=TaskQueue.DEFAULT, payload=SendDigest, deadline=timedelta(seconds=60), retry=RETRY_TRANSIENT)`. The name is `slice.task` and never changes while messages may carry it. The payload is a `TaskPayload` (frozen, unknown fields ignored); a task acting in a home uses `HomeTaskPayload` and opens its transactions in `payload.scope()`. A new field is optional. A secret travels as a `TaskSecret` field and is masked wherever the payload is kept.
- **Retry policy:** `NO_RETRY` (the default choice for anything that charges or sends) or `RETRY_TRANSIENT` — up to 5 deliveries after a failure of the home, the bucket, Valkey, the network or the deadline; a `RetryPolicy` names other failures explicitly. A retry is a redelivery after 5 s doubling to 120 s, jittered; no worker slot waits through it. Every task must tolerate running twice.
- **Bind** it in the slice's build: `TaskHandler(SEND_DIGEST, digests.send)` in `FeatureParts.task_handlers`. `build_task_system(valkey, registry, tracer_provider)` makes the brokers and the `TaskSender` first, so a handler built with `services.tasks` can queue further work; composition then registers every handler of every slice in every role (`TaskSystem.register`), and a name declared twice stops the start.
- **Send:** `await sender.send(SEND_DIGEST, SendDigest(...))` within 50 ms, or `TaskQueueUnavailableError` (503 `queue_unavailable` with `Retry-After`) when Valkey is silent or the stream holds 500 000 tasks. Work that must not be lost — money, email — goes through the outbox. A periodic task (`kind=TaskKind.TICK`) goes through `send_tick(task, payload, *marker)`, which skips the tick while the previous one with the same marker is in flight; a failed tick is dropped, the next one does its work.
- **Run:** `consume_queue(broker, stop)` runs one queue's tasks in a worker process (`critical` 16 at once, `default` 5, `bulk` 3, `meeting` 3) and drains for up to 20 s when `stop` is set. The handler runs within its declared deadline. A worker renews the lease of every message it holds; a message idle 120 s belongs to a dead worker and is delivered again.
- **Dead letter** (`shosai:dead-letter:<queue>`, 7 days): the last failed delivery, a failure the policy does not retry, a task abandoned on its last delivery, a message of an unknown task or one that is not a task. An entry keeps the task, deliveries, error type and text, trace and request ids and the payload with secrets masked; it is counted in `shosai_task_dead_letters_total{queue, reason}`, unknown tasks also in `shosai_task_unknown_total{queue}` (§16.4).
- **Observability:** one log line per run with its outcome, delivery and duration, the stack on failure; `task_name`, `task_id`, `request_id` and the payload's ids on every line of the run; one consumer span per run continuing the sender's trace, with the error type only; `shosai_task_runs_total{queue, task, outcome}`, run and wait histograms, send failures, skipped ticks, leases lost or capped, Valkey failures. `QueueMonitor.refresh()` sets the depth, oldest-task age and dead-letter gauges; one process (the scheduler) runs it.

## Events

`core/events` passes facts between slices through the transactional outbox and one task per subscriber (§8.1, §12). An event exists exactly when its effect does; each subscriber applies it once.

- **Declare** an event once, in the producing slice's `contracts` module: a `DomainEvent` subclass with `event_type: ClassVar[str] = "meetings.note.enhanced"` (`slice.object.happened`, past tense) and `version: ClassVar[int] = 1`. A field is an id, a number, a flag, a time, an enum or an `EventCode` (`[a-z0-9_.:-]{1,64}`), or a tuple or frozenset of them; anything else — `str`, a dict, a nested model — fails when the class is defined, so no email, name or title enters an event. A new field is optional; a change consumers cannot read gets a new event type.
- **Write** it in the effect's transaction: `await outbox.add(session, NoteEnhanced(...))` with the `EventOutbox` the slice receives. The writer commits nothing; it takes the home and the account and company of the transaction (`HomeTransactions` records them in the session), the trace context and the request id. A class composition did not list, a read-only transaction or a session not opened by `HomeTransactions.begin` is refused.
- **Subscribe** in the consuming slice: `EventSubscription(consumer="search.index_note", event=NoteEnhanced, queue=TaskQueue.DEFAULT, deadline=timedelta(seconds=30), handle=…)`. The consumer name never changes: it keys the delivery marks and names the delivery task `events.<consumer>`. The handler receives the delivery's session and a `ReceivedEvent` (event, id, version, time, scope) and writes its effect in that session only; the mark `processed_events (consumer, event_id)` commits with it, so a redelivered event changes nothing. The transaction runs in the event's home unless the subscription names the home of its effect (`home=Home.EU` for the directory and platform tables, ADR 0005); then the mark is written there as well, and `ReceivedEvent.scope` still names the event's home. Like every transaction it holds no external call: such work goes to a task or a row the slice processes later.
- **Compose:** a slice lists its event classes in `FeatureModule.events` and its subscriptions in `FeatureParts.subscriptions`. The outbox exists before any slice is built and knows only the classes (`EventTypes`); `EventCatalog(events, subscriptions)` then refuses a type listed twice, a consumer subscribed twice and a subscription to an unlisted event, and `event_task_handlers(EventResources(...), sender)` gives the relay, the purge and one delivery task per subscription, registered in every role.
- **Relay** (`events.relay_outbox`, `critical`, a tick per home every 5 s): a pass claims up to 100 due rows for 30 s (`FOR UPDATE SKIP LOCKED`) and commits, queues one delivery per subscriber outside any transaction, then marks them published. A tick runs passes while each claims a full batch, and starts none after its 15 s budget; `shosai_outbox_relay_tick_passes`, `shosai_outbox_relay_tick_rows` and `shosai_outbox_relay_budget_exhausted` show how hard it works, the last one being the revisit trigger of §12. A row whose deliveries were not queued — Valkey out, a delivery task missing from the process, an event type a newer image wrote — waits `min(2^attempts, 300)` s and comes back; it is never dropped. Each home relays on its own, so an outage of one never stops the other. The relay opens a producer span per event as the child of the producer's trace, so the delivery continues that trace and carries its `request_id`.
- **Delivery:** a consumer this process does not know is an unknown task and is dead-lettered and counted; a payload its class cannot read is dead-lettered without running; failures of the home, the bucket, Valkey or the network get up to 5 deliveries.
- **Purge** (`events.purge_outbox`, `bulk`, daily per home): published events after 7 days, delivery marks after 14, in batches of 5 000; unpublished events stay.
- **Observability:** `shosai_outbox_published_total{home}`, `shosai_outbox_held_back_total{home, reason}`, `shosai_outbox_purged_rows_total{home, table}`, `shosai_event_duplicate_deliveries_total{consumer}`; `OutboxMonitor.refresh()` sets `shosai_outbox_pending{home}` and `shosai_outbox_oldest_age_seconds{home}` (the "outbox events older than 5 min" monitor, §16.4); the scheduler runs it. Task metrics of the deliveries carry the task `events.<consumer>`.

## Idempotency and pagination

- **Effect keys** (`core/idempotency`, table `effect_keys` in every home): `services.effects.once(session, EffectKey(scope, key, fingerprint), Outcome, effect)` claims the key, runs the effect and stores its outcome in the caller's transaction, so key, effect and outcome commit together. A repeat returns the stored outcome with `replayed=True` and writes nothing; two transactions with one key apply it once (the second waits on the first one's row). The same key with another fingerprint is 422 `idempotency_key_reused`. `EffectScope("agent.turn", keep=…)` names the kind of effect and keeps its keys for at most 90 days — longer than any retry, redelivery or re-entry; an expired key is taken over as new, and `idempotency.purge_keys` removes expired keys daily per home. The outcome is a small reference (an id, a status), at most 8 KB. The effect must not swallow its own failure: a key committed without an outcome is a defect, never replayed.
- **`Idempotency-Key`** (`core/idempotency/http.py`): `key: IdempotencyKeyHeader` declares the required header (1–128 of `A–Z a–z 0–9 . _ : -`), so OpenAPI shows it and a missing or malformed key is 422 before the handler. The handler binds it to the account (`account_key(user_id, key)`) and fingerprints the request body (`fingerprint_of(body)`).
- **Pages** (`core/pagination`): a collection answers `Page[Item]` — `{"items": […], "next_cursor": "…" | null}`. `page: PageParameters` reads `limit` (1–100, default 50) and `cursor`; `page_parameters(default, maximum)` sets other bounds. A limit outside them is 422 before the handler. `Keyset((column, …, unique_column), descending=…)` turns a statement into the range after the cursor's position plus one row, and `page_of(rows, request, codec, item, position)` builds the page. `CursorCodec("slice.collection", Position)` makes the opaque cursor; a cursor of another collection or format, or one that does not fit `Position`, is 422 `invalid_cursor`. Sort columns are NOT NULL, share one direction and are indexed in that order.

## AI provider port

- **Calling a model** (`core/ai`, ADR 0034): a slice calls `services.ai.chat`, `stream_chat`, `embed`, `rerank` or `generate_image` with a `CallContext`, a `ModelRoute` and a request; nothing else in the backend creates a provider client (import-linter "Provider SDKs only in core.ai", and `tests/architecture/test_provider_hosts.py` for raw HTTP). `CallContext` names the payer — a user's `TenancyScope` or a `PlatformAccount` (`landing_demo`, `help_assistant`, `system`, charged in the EU home) — the effect key, the feature label, the `CallClass` (`essential`, `standard`, `expensive`), the origin, an optional deadline and the cross-border consent. A call of the RU home without that consent is refused (`consent_required`, nfr-14); a model without a price for each unit its kind is charged in is refused before it is sent (`model_unpriced`, ADR 0035); failures are `AiCallError` with a closed code. Retries, breakers, fallbacks along the route and spend admission come with F6 steps 5 and 6.
- **Cost rows** (`provider_costs`, every home, monthly partitions kept 5 years): each call writes one row in the payer's home through the effect-key ledger (scope `ai.cost`, 35 days), so a replayed effect key writes nothing and runs no settlement again (inv-9). The amount is the provider's reported `usage.cost`, else units times the prices in force (`provider_prices`, EU home, cached 60 s); rubles at the latest USD/RUB rate (`exchange_rates`, EU home, fetched from the Central Bank every 6 h by the periodic job `exchange_rates.fetch`), empty while no rate exists. A slice adds its debit as a `CostSettlement` in `FeatureParts.cost_settlements`; it runs in the row's transaction. A row its home refuses goes to the task `ai.record_cost`; with Valkey out too it is lost and counted in `shosai_ai_calls_without_cost_row_total`, as is a stream closed before its usage arrived.
- **Settings:** `OPENROUTER_API_KEY` (without it the provider is disabled; the gate requires it outside development), `OPENROUTER_BASE_URL` (empty: OpenRouter's own), `CBR_DAILY_URL`.
- **Tests** use `tests/doubles/openrouter.py`: `ScriptedOpenRouter` answers as OpenRouter over an HTTPX mock transport, so the real adapter runs with no network.

## Periodic jobs and due rows

- **A periodic job** (`core/schedule`, §12): `PeriodicJob(task, every, homes)` names a tick task with a `HomeTaskPayload`, an interval of at least a minute and its homes (both by default; platform jobs name the EU home); the job's name is the task's. The scheduler walks each home every 5 s: one conditional update claims the due jobs of `schedule_runs` (`last_run_at` NULL or older than the interval) and skips rows another walk holds, the claims commit, then each tick is queued with `send_tick`. Two scheduler processes never queue a job twice in one interval; a missed interval runs once, however long; a deploy does not re-run a daily job; a tick that could not be queued gives its claim back, and one skipped because the previous run is in flight keeps it. Core's daily purges and partition upkeep are periodic jobs (`composition/schedule.py`). Metrics: `shosai_periodic_job_runs{job, home, outcome}` and `shosai_periodic_job_last_queued_timestamp_seconds{job, home}`.
- **A due-row source**: `DueRowSource(sweep, every, homes)` queues the slice's sweep tick every few seconds per home. The sweep calls `claim_due(session, DueRows(table, key, run_at, pending), limit=…, lease=…)`: up to `limit` pending due rows, oldest first, skipping rows another sweep holds, their `run_at` moved forward by the lease; the sweep moves a finished row out of pending, and a row whose sweep died comes due again when the lease ends. The table needs a unique key, a NOT NULL due column and an index on (due column, key) where pending.
- A job or a source whose task the process did not register, or one declared twice, stops the start at the step `schedule`.

## Process roles

One console command, `shosai`, runs one role per process on one uvloop event loop (§5). Composition (`composition/`) builds what the role needs; `entrypoints/cli.py` only parses the command line.

| Command | Serves | Runs |
|---|---|---|
| `shosai api` | the public app on `HTTP_PORT`: every slice's HTTP routes and `GET /v1/health` | — |
| `shosai ws` | the public app of the WS gateway on `HTTP_PORT`: every slice's WebSocket routes and `GET /v1/health` | — |
| `shosai workers --queue Q` | — | TaskIQ's receiver of queue `Q` (`critical`, `default`, `bulk`, `meeting`) |
| `shosai scheduler` | — | the loops: the outbox relay of each home every 5 s, the walk of periodic jobs of each home every 5 s, every slice's due-row sources, the queue and outbox gauges every 15 s, every slice's loops |
| `shosai migrate upgrade` / `current` | — | Alembic for both homes, RU first; logs each home's revision |

- **Ops port.** Every long-running role also serves `OPS_PORT`, which the edge never proxies: `GET /livez` (200 while the event loop runs; checks nothing else), `GET /readyz` (200 while the process takes work, 503 while it starts or drains; the body names `homes.ru`, `homes.eu`, `valkey`, `cache`, `storage` and each slice's probes `ok` or `down`, each within 2 s) and `GET /metrics` (the process registry; OpenMetrics when asked, for exemplars). A dependency that is down never fails readiness (F1-C2): it is alerted through metrics.
- **Start**, each step named in the one critical line when it fails, exit code 1: settings and the production gate → logs, metrics, traces → the ops server → `features` (no slice listed twice) → `databases` (one engine per home; another home's database or a schema behind the code stops the start, a home out of reach does not) → `shared_services` → `tasks` → `feature:<name>` for each slice → `events` (catalog, every task registered) → `schedule` (periodic jobs and due-row sources, each named once, each task registered) → `probes` (each name once) → the role. Valkey, the cache and the bucket are not contacted at start, so their outage never stops it (§13.2).
- **Stop** on SIGTERM or SIGINT: readiness turns 503 at once → the role drains (in-flight requests up to 20 s, running tasks up to 20 s — the rest return to their queue after the lease — and the loops' current iteration) → the slices, the clients and the engines close → the ops server stops → spans are exported within 5 s and the log queue written out. The stop fits a 30 s container grace period (F4 sets `stop_grace_period: 30s`). The public server keeps an idle connection 75 s, so the edge's idle upstream connections (NGINX: 60 s by default) must stay shorter. A server or worker that ends by itself stops the process with exit code 1, so the orchestrator restarts it.
- **Loops** (`core/runtime/loops.py`) run at start and then once per interval, never as a backlog; an iteration has a deadline (10 s by default), each is recorded in `shosai_loop_iteration_duration_seconds{shosai_loop_name, error_type}`; a failing one is logged with its stack and recorded under its exception class (`RuntimeError`, `TimeoutError` past the deadline), and the loop goes on. `shosai_loop_last_success_timestamp_seconds{shosai_loop_name}` and `shosai_loop_interval_seconds{shosai_loop_name}` let an alert tell a stuck loop from a slow one. The names follow OpenTelemetry's naming rules (F1 audit OD-3). A loop only queues tasks or reads gauges; workers do the work (§4.2).

### Run locally

With the local environment up ([docs/development.md](../docs/development.md), "Run the backend"):

```bash
uv run --env-file ../.env shosai migrate upgrade
uv run --env-file ../.env shosai api
OPS_PORT=9101 uv run --env-file ../.env shosai scheduler
OPS_PORT=9102 uv run --env-file ../.env shosai workers --queue critical
```

Several roles on one machine need different ports; in containers each process has its own.

## Adding a slice

A slice is a package `features/<name>/` whose public surface is `contracts.py` (the import-linter contract "Features meet through contracts"). Inside, `channels` (HTTP, WS, tasks, consumers) → `application` → `domain`, with `infrastructure` implementing the domain's ports; the domain imports no framework (the "Pure slice domain" contract).

1. Declare one `FeatureModule` (`core/features.py`) in the slice: `name` (its package), `models`, `events`, `production_checks` and `build`.
2. `build(services: CoreServices)` is an async context manager entered at start in every role and left at stop. It receives the process's `transactions`, `tasks` (the sender), `outbox`, `effects` (the effect-key ledger), `ai` (the provider port), `exchange_rates`, `cache`, `objects`, `uploads`, `locks`, `rate_limiter`, `valkey`, `settings`, `registry` and `tracer_provider`, opens the slice's own clients, and yields `FeatureParts`: `http_routers`, `ws_routers`, `task_handlers`, `subscriptions`, `loops`, `probes`, `periodic_jobs`, `due_sources` and `cost_settlements`. Each role uses only its part; every role registers every task.
3. Add the module to `FEATURES` in `composition/features.py`. Its models join the metadata Alembic and the schema test compare; its routes join the route snapshot (`tests/composition/public_routes.json`, updated in the same commit) and the native-contract gate holds every route of the shipped macOS and Windows clients that it serves to the draft contract, whatever the slice's name ([contracts/README.md](../contracts/README.md)). A native route the slice starts to serve leaves `tests/composition/native_routes_not_served.json` in the same commit; that list must be empty before cutover.
4. Register every source of model-facing text in `tests/model_facing/registry.py`, and add the slice's variables to `.env.example` section 2.

`tests/composition/fixture_features.py` shows two slices that use every part; `tests/composition/test_platform.py` proves each part is wired.

## Tests

Tests that touch the databases need the local environment ([docs/development.md](../docs/development.md)); all tests read only `TEST_*` variables ([ADR 0009](../docs/adr/0009-test-databases-claimed-by-advisory-lock.md)), listed with local values in section 3 of [`.env.example`](../.env.example).

```bash
../scripts/local-env.sh up
cp -n ../.env.example ../.env      # once
uv run --env-file ../.env pytest
```

- The session fixture `run_slot` claims a free prepared slot `shosai_test_<N>` in both homes with an advisory lock, so parallel runs never share one, and gives a direct migration-role connection per home. A crashed run's lock is released with its connections. The pytest summary names the slot.
- The harness refuses to start if a host is not loopback (the bucket's endpoint included), a database name is not `shosai_test`, the claimed database is not a prepared test database, or a database, Valkey or cache `TEST_` URL equals a runtime URL.
- On claim the harness returns the slot to the state F3 prepares — it drops a crashed run's objects and the extensions the migration role created, and restores default privileges, rights on the `public` schema and on the database, and database settings. At the end it fails the run, naming the objects, if the catalog of either home differs.
- After the claim both homes are upgraded to the head with the production runner; at the end they are downgraded to the base, the version table is dropped, and only then are the catalogs compared.
- The slot is also database `N` of Valkey and of the cache and the prefix `tests/slot-<N>/` of the bucket. A test that writes there takes `valkey`, `redis_cache` or `bucket` (`tests/harness/shared_services.py`), which empty the slot's part after it; a run that ends with keys or objects left fails.
- A test that writes application data takes the `homes` fixture (`tests/harness/database_access.py`): the `api` database access of the run, emptied of application data after the test. `open_database_access(urls, ProcessShape(...))` builds the access of another role, pool, tracer, history or clock.

### Model-facing text

Everything a language model reads is English (CLAUDE.md "Prompts"). A slice registers each source of such text in `tests/model_facing/registry.py` in the same commit that adds it; the test fails on any letter outside the Latin script, except declared endonyms such as `Русский`.

Docstrings are English across the backend (CLAUDE.md "Language"), because tools publish them: FastAPI puts them into OpenAPI, Pydantic into the `description` of a JSON schema, agent frameworks and MCP into tool descriptions. `tests/architecture/test_docstrings_english.py` checks every docstring; comments stay Russian.

## Gates

Run from `backend/` once a task is complete (CLAUDE.md "Checks"):

```bash
uv run ruff format --check . && uv run ruff check .
uv run mypy .
uv run lint-imports
uv run --env-file ../.env pytest --cov
uv run python-doctor . --score   # must print 100
```
