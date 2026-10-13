# F1 — Backend foundation: package plan

Prompt: [prompts/F1-backend-foundation.md](../prompts/F1-backend-foundation.md). Status: [STATUS.md](../STATUS.md). Decision records: [ADR 0008](../../adr/0008-error-envelope-with-compatible-detail.md) (error envelope), [ADR 0009](../../adr/0009-test-databases-claimed-by-advisory-lock.md) (test databases), [ADR 0010](../../adr/0010-home-scoped-revisions-in-one-alembic-history.md) (home-scoped migrations, start check), [ADR 0011](../../adr/0011-rate-limits-gcra-in-valkey.md) (rate limits), [ADR 0012](../../adr/0012-http-metrics-in-the-request-boundary.md) (HTTP metrics), [ADR 0013](../../adr/0013-psycopg-driver-behind-pgbouncer.md) (PostgreSQL driver), [ADR 0014](../../adr/0014-one-object-store-in-russia.md) (one bucket in Russia), [ADR 0015](../../adr/0015-aiobotocore-instead-of-aioboto3.md) (S3 client), [ADR 0016](../../adr/0016-own-task-broker-on-valkey-streams.md) (task broker).

The package builds the `backend/` project every slice stands on: configuration, logging and telemetry, the HTTP shell and the error envelope, home-aware database access with migrations and RLS groundwork, Valkey, cache and object storage clients, TaskIQ, the outbox, the four process roles and the test harness. It contains no feature code.

## 1. Facts this plan rests on

### 1.1 Inputs from other packages

| Source | Fact |
|---|---|
| F3, [development.md](../../development.md), [ADR 0001](../../adr/0001-local-environment.md) | Two PostgreSQL 18 servers (RU `15432`, EU `15433`), each behind PgBouncer in transaction mode with `max_prepared_statements = 0` (RU `16432`, EU `16433`); no statement may stay prepared on a server connection (ADR 0013). Roles `shosai_migrator` (owner, direct) and `shosai_app` (no `SUPERUSER`, no `BYPASSRLS`, through PgBouncer). Slots `shosai_test_1…8` with the same name on both servers. Valkey 9.1 (`noeviction`, AOF), Redis cache (`allkeys-lru`), SeaweedFS with buckets `whisperer-ru` and `whisperer-eu`. Connection variable names in `.env.example` section 2 are F1's to fix. |
| D1, [contracts/README.md](../../../contracts/README.md) | `GET /v1/health` is the only client-facing health route (web connectivity probe, reads `res.ok`); `/health`, `/ready`, `/v1/ready` are the draft's own probes, excluded. Native clients read only the top-level `detail`; its type is fixed per route. Unknown `/v1/...` paths answer 404 with JSON. The harness is added to `backend/` as a path dependency and checks a slice's routes. |
| D4, [FEATURE_MAP.md](../FEATURE_MAP.md) | F1 owns the draft's `core/` (except parts named elsewhere), `composition/`, `entrypoints/`, `main.py`, `config.py`, `i18n/`, `api/health.py`, `api/deps.py`, `services/crypto`, `services/domain_events`, `tasks/outbox_relay.py`, tasks `messaging.relay_outbox` and `messaging.purge_outbox`, and draft specifications 009, 010, 013, 017, 018, 020, 035. NATS is replaced by outbox + TaskIQ. |
| D3, [DATA_MAPPING.md](../DATA_MAPPING.md) | `outbox_messages` and `processed_events` start empty in v2; nothing is migrated into F1's tables. |
| F6 prompt | F6 builds the provider port, email and the periodic-job registry on `schedule_runs` on top of F1's scheduler process. |

### 1.2 The draft, for lessons

Read in `/root/whisperer/backend/src/meetassist/`. Each lesson becomes a rule here.

| Draft fact or incident | Rule in v2 |
|---|---|
| One `Settings` class of ≈ 260 fields reading `.env` (`config.py:16`); `backend/.env` of v2 holds the draft's production values | Settings are read from the environment only, never from a dotenv file; they are built once per process and passed in, no cached global getter |
| `ENVIRONMENT` unset in production silently disabled every safety check (spec 009) | A production gate refuses to start on an unsafe configuration and names the setting |
| Proxy trust by uvicorn `FORWARDED_ALLOW_IPS="*"` (spec 010) | Trusted proxy addresses are explicit; production refuses to start without them |
| `/health` was hard-coded green during outages (spec 013) | Liveness answers for the process; dependency state is checked with a 2 s timeout and reported |
| Silent 500s; per-call engines; DB session held across LLM streams (spec 017) | One stack-traced log line per unhandled error; one engine per home per process; explicit short transactions |
| `create_all` in production and no head check (spec 035) | Alembic is the only schema source; a process refuses to start unless every home is at head |
| Background loops ran in every API replica (spec 020) | Loops run only in the scheduler process |
| Pool exhausted by 176 overlapping relay ticks (`core/tasks/ticks.py:10`) | Periodic enqueues use tick markers; one tick per job in flight (§4.3) |
| `pool_pre_ping` off for a 45 ms round trip; `pool_recycle` below the provider's idle timeout (`config.py:64-92`) | Same settings, per home |
| No asyncpg statement-cache setting; no PgBouncer in the draft | psycopg without server-side prepared statements, one round trip per statement (ADR 0013); verified under concurrency |
| Managed Valkey cuts blocking reads at 5 s and raises `TimeoutError` (`core/tasks/broker.py:117`) | Blocking reads ≤ 2 s; timeouts and connection errors handled alike |
| Leases, 5 deliveries then dead letter, no instant retries (`core/tasks/lease.py`, `broker.py:179`, `broker.py:776`) | Carried over, in our own broker on TaskIQ's `AsyncBroker` (ADR 0016) |
| Dead letter stored password-reset links in plain text (`core/tasks/dead_letter.py:9`) | Dead-letter entries redact sensitive payload fields |
| A worker answered "task is not found" for domain tasks (`entrypoints/worker.py:48`) | Every role registers every task; an unknown task is dead-lettered and alerted (§14 rule 9) |
| Fail-open leader lock risked double charges (`core/metrics.py:107`) | A lock caller must choose fail-closed or fail-open explicitly |
| `HTTPException` became 500 under a yield dependency with `BaseHTTPMiddleware` (`core/exceptions.py:95`) | Pure ASGI middlewares only |
| Unhandled 500s probably left without `X-Request-ID` (middleware order) | The request-id middleware is outermost and renders the 500 itself (ADR 0008) |
| Tests had no production guard and once wrote to the production Redis (`tests/conftest.py:12, 56`) | ADR 0009 |
| A Starlette upgrade broke the metrics instrumentator: 500 on every request (`requirements.txt` header) | HTTP metrics are recorded by the request boundary without the instrumentator (ADR 0012); a test runs them with the native tracing on every run |
| mypy targeted 3.11 and silently checked nothing (`pyproject.toml`) | mypy targets 3.14 and covers `src`, `tests` and `migrations` |
| Feature `on_startup` hooks were never called (`composition/registry.py:176`) | The feature registry is exercised by tests with fixture features |
| `utils/` mixed unrelated helpers | Not carried as a module: each helper moves with the slice that first uses it |
| `i18n/` holds the 16 locales, Accept-Language parsing and email catalogs | Locales and Accept-Language go to `core`; email catalogs go to F6 and the slices |
| `services/crypto.py`: Fernet key ring `FERNET_KEY` + `FERNET_KEYS_PREVIOUS` | Carried with the same variable names, so migrated ciphertexts decrypt (DATA_MAPPING S-3) |

### 1.3 Versions and tool checks (2026-10-01)

Latest stable releases on PyPI, pinned by `uv.lock` when each step adds them:

| Package | Version | Package | Version |
|---|---|---|---|
| fastapi | 0.142.2 | taskiq (ADR 0016; taskiq-redis 1.2.4 dropped) | 0.13.0 |
| uvicorn | 0.54.0 | redis (redis-py) | 8.1.0 |
| pydantic / pydantic-settings | 2.13.5 / 2.15.0 | aiobotocore (ADR 0015; aioboto3 15.5.0 dropped) / types-aiobotocore[s3] | 3.9.2 / 3.9.2 |
| sqlalchemy | 2.1.2 (step 4) | structlog | 26.1.0 |
| psycopg[binary] (ADR 0013; asyncpg 0.31.0 dropped) | 3.3.6 | opentelemetry-sdk / exporter-otlp-proto-http | 1.45.0 |
| alembic | 1.20.0 | opentelemetry instrumentations | 0.66b0 |
| httpx | 0.28.1 | prometheus-client (the instrumentator was removed, ADR 0012) | 0.26.0 |
| cryptography | 50.0.2 | ruff / mypy / import-linter | 0.16.10 / 2.4.0 / 2.15 |
| pytest / pytest-asyncio / pytest-cov | 9.1.1 / 1.4.0 / 7.1.0 | hypothesis / python-doctor / pip-audit | 6.168.3 / 2026.5.11 / 2.10.1 |

Checked in the packages themselves:
- FastAPI 0.142 has native OpenTelemetry (`FastAPI(telemetry={...})` with `tracing`, `metrics`, `logs`, `auto_configure`, `exclude`).
- TaskIQ 0.13 runs a receiver inside an existing event loop (`taskiq.api.run_receiver_task`) and ships `OpenTelemetryMiddleware`.
- taskiq-redis 1.2.4 `RedisStreamBroker` takes `idle_timeout`, `maxlen`, `xread_block`; its default `consumer_id="$"` skips tasks enqueued before the group exists, so v2 sets `"0"`, as the draft did. It has no lease extension or delivery limit; those are built here.
- Checked in step 6 (2026-10-02): taskiq-redis builds a connection pool per broker from a URL, enqueues without a deadline, trims unfinished tasks with `MAXLEN ~`, survives no connection error, `TimeoutError` or `NOGROUP`, and acknowledges without deleting (ADR 0016). TaskIQ's receiver acknowledges `WHEN_EXECUTED` before `post_execute` runs, logs an unparseable body at WARNING, acknowledges an unknown task with a warning, and its parameter parser logs rejected input; its decorated-task constructor renames the function and sets it on its module; its `OpenTelemetryMiddleware` needs psutil and records the exception text. Valkey 9.1.2 has no `XACKDEL`; `XCLAIM … IDLE … JUSTID` sets the idle time without counting a delivery.
- Checked in step 7 (2026-10-02): SQLAlchemy 2.1 deprecates `Result.tuples()` (a row unpacks itself) and types `AsyncSession.execute` of a DML statement as `Result`, so a row count is read through the session's connection; PostgreSQL's `power()` raises "value out of range" past 2^1023; pydantic 2.13 keeps a PEP 695 alias such as `EventCode` as the field's annotation, so the event-field rule can name it.
- import-linter 2.15 supports wildcard module expressions, `independence`, `protected` and `unmatched_ignore_imports_alerting`.
- Python 3.14's standard library has `uuid.uuid7()`; no extra package for UUIDv7.
- aioboto3 15.5.0 (2025-10-30) is its latest release and pins `aiobotocore==2.25.1` and `botocore<1.40.62`; aiobotocore 3.9.2 (2026-10-01) is current (checked 2026-10-02, ADR 0015).
- opentelemetry-instrumentation-redis 0.66b0 instruments one client (`instrument_client(client, tracer_provider=…)`) and records a command with its arguments replaced by `?`.
- redis-py 8.1 retries a failed command up to 10 times by default and drops a connection whose reply was interrupted by a cancellation; v2 turns the retries off.
- Checked in step 8 (2026-10-02): uvloop 0.23.0 (2026-10-01) has CPython 3.14 wheels. uvicorn 0.54's `Server.serve` replaces the SIGTERM and SIGINT handlers and raises the signals again after serving, and its `startup` calls `sys.exit` when it cannot bind; `Config(access_log=False)` detaches the `uvicorn.access` logger from the root for the whole process; `forwarded_allow_ips=None` falls back to `FORWARDED_ALLOW_IPS` or `127.0.0.1,::1`, while `[]` trusts nobody. asyncio's `remove_signal_handler` installs the default handler, not the one before it. Alembic names each step in its log line by the step function's `__name__`, which step 4's `ScopedStep` lacked: every live `migrate upgrade` printed a logging error (fixed, with a test).

## 2. Decisions

Confirmed by the owner on 2026-10-01:

| ID | Decision | Record |
|---|---|---|
| F1-D1 | Error body `{"error": {code, request_id, params?, fields?}, "detail": …}`; `detail` defaults to the code and keeps the draft's per-route shape on native routes; `X-Request-ID` on every response including 500 | ADR 0008 |
| F1-D2 | Test slots claimed by `pg_try_advisory_lock` in both homes; tests read only `TEST_*` variables; loopback and name guards; truncation per test; upgrade → tests → downgrade → catalog fingerprint unchanged | ADR 0009; CLAUDE.md updated |
| F1-D3 | One Alembic history; a revision may declare `applies_to`; EU-only tables do not exist in the RU home | ADR 0010; §6 updated |
| F1-D4 | Own GCRA limiter in Valkey through redis-py instead of slowapi | ADR 0011; §18.2 updated |

Confirmed by the owner on 2026-10-02:

| ID | Decision | Record |
|---|---|---|
| F1-D5 | HTTP metrics are recorded by the request boundary from the route FastAPI has already matched, under the names, help texts, labels and buckets of prometheus-fastapi-instrumentator 8.1.0, which is removed; label values come from closed sets | ADR 0012; §16.1, §16.7, §18.2 updated; was open item F1-O1 |
| F1-D6 | psycopg 3 instead of asyncpg: with PgBouncer's prepared statements off, asyncpg costs two round trips per statement (6 for a scoped read, 270 ms to the RU home) and psycopg one (4, 180 ms, §3); row decoding within 15% | ADR 0013; §16.1, §18.2 updated; ADR 0001 amended |
| F1-D7 | The start check passes a schema newer than the code (a revision this code does not know): migrations only expand, so a rolled-back image starts; a schema behind the code stops the start | ADR 0010 item 6 amended |
| F1-D9 | Object storage exists only in Russia: one bucket for both homes and the platform; one storage configuration `S3_*` and one client per process instead of `HOME_<H>_S3_*` and a client per home | ADR 0014; nfr-4, §4.1, §4.2, §6, §8.1, §9, §13.1, §18.2, §19, §20, §22 and DATA_MAPPING 6.2 updated |
| F1-D8 | A home out of reach does not stop the start (§13.2): its transactions get 503 until the check passes, repeated at most every 5 s before its transactions; another home or a schema behind found later closes the home with a critical log and `shosai_db_home_state` | ADR 0010 item 6 amended |
| F1-D10 | aiobotocore 3.9.2 is the S3 client instead of aioboto3, whose latest release pins aiobotocore 2.25.1 and botocore of October 2025; the ports need nothing aioboto3 adds | ADR 0015; §18.2 updated |
| F1-D11 | The tests' S3 endpoint must be loopback and may equal the development one: tests share the one local bucket and write only under `tests/slot-<N>/`; the rule that a `TEST_` URL differs from every runtime URL covers databases, Valkey and the cache | ADR 0009 item 2 amended |
| F1-D12 | The production gate requires TLS for Valkey (`rediss://`): the managed Valkey is outside the plane's containers and carries task payloads, transcript lines and meeting state; the Redis cache inside the plane needs none | §15 updated |
| F1-D13 | The task broker is our own subclass of TaskIQ's `AsyncBroker` over the process's one Valkey client; taskiq-redis is not used: its broker would need `kick`, `listen`, acknowledgement, start-up and its pool overridden | ADR 0016; §18.2 updated |

Design choices made in this plan, open to objection at plan review:

| ID | Choice | Why |
|---|---|---|
| F1-C1 | Python package `shosai` under `backend/src/` | Product name; the draft's `meetassist` is legacy |
| F1-C2 | Readiness reports dependencies but fails only while the process starts or drains (§3.11) | All processes share the same dependencies; failing readiness on the RU database would pull every process from the edge and stop EU users too, against §13.2 |
| F1-C3 | Every role serves `/livez`, `/readyz` and `/metrics` on an internal ops port; the public app serves only `GET /v1/health` | Metrics and dependency state are never reachable through the edge; workers and the scheduler need an HTTP endpoint for Prometheus anyway |
| F1-C4 | The application-wide 120 requests per minute per IP of draft spec 010 is not carried; per-route limits stay with their slices | The edge already bounds 50 req/s per IP (§4.3), and a company of 30 seats behind one office address would hit 120/min |
| F1-C5 | `processed_events` rows kept 14 days, published outbox rows 7 days (§8.1) | A delivery mark must outlive any redelivery of its event |
| F1-C6 | Cross-tenant sweeps under RLS are not decided here; S02 decides with its first policies | §7 asks for a dedicated role, §14 rule 2 for one pool per database per process; the trade-off depends on S02's policies |
| F1-C7 | A cache call waits at most 20 ms; TTLs are shortened at random by up to 10% | The cache container is next to the processes; past 20 ms a database read is the faster path. Jitter keeps entries written together from expiring together (caching skill) |
| F1-C8 | Rate-limit state keys hold a BLAKE2b digest of the subject, not the address or the user id | Keys of a fixed length, and no client address or id in Valkey's keyspace |
| F1-C9 | The storage adapters take an optional root prefix; tests confine themselves to `tests/slot-<N>/` with it, production works at the root | A slice's own keys stay inside the run's prefix in tests without test-only code in the slice |
| F1-C10 | `MultipartUploads.list_parts` is part of the port | The draft's resumable desktop upload asks the bucket which parts it accepted; only the bucket knows for sure |
| F1-C11 | A retry is a redelivery owned by the broker (§4.3): the failed message goes back with an idle time that makes it claimable after 5 s doubling to 120 s, jittered to 50–100%; every delivery counts toward the five | No worker slot waits through the pause, the limit holds on every re-entry path (§14 rule 6), and a restart does not lose the retry |
| F1-C12 | The dead letter is a Valkey stream per queue, entries kept 7 days and about 1 000 per queue, at most 32 KB each; `TaskSecret` fields masked, sensitive keys redacted, no payload for an unknown task or one that does not match its model | Valkey does not evict, so the bound protects the queues; inspection and replay keep what they need without secrets (draft lesson) |
| F1-C13 | Trace context crosses the queue through our own middleware: W3C context in the labels, one consumer span per run with the error type only | TaskIQ's middleware records the exception text (§16.8) and needs psutil; HTTP and Valkey spans already cover the send |
| F1-C14 | The stream holds only unfinished tasks: success acknowledges and deletes in one script; the full stream refuses with 503 | The stream's length is the depth, finished payloads never linger, and backpressure replaces silent trimming |
| F1-C15 | Concurrency per worker process: `critical` 16, `default` 5, `bulk` 3, `meeting` 3; drain 20 s | The draft's production values against a pool of 5 per home; step 8 checks the drain against the container's stop grace |
| F1-C16 | The consumer's declaration sets the deadline, not a label of the message; a message of an unknown task is dead-lettered at once | A producer cannot change a worker's limits; §14 rule 9 deploys consumers first, so an unknown task is a mistake to alert on, not to wait out |
| F1-C17 | A delivery runs in the tenancy scope of the effect's transaction: the outbox row keeps its account and company, taken from the session `HomeTransactions` opened, never passed by the caller | The consumer's effect lands under the same row-level security as the producer's; a caller cannot write an event of another tenant |
| F1-C18 | One delivery task per subscription, `events.<consumer>`, carrying the event | An unknown consumer is an unknown task, so step 6 already dead-letters and counts it; task metrics per consumer; the delivery reads nothing back from the outbox, one round trip less to the Russian home. Events hold no personal data, so the copy in Valkey adds none (§6) |
| F1-C19 | An event type the image does not list is held back with the backoff, not published or dropped; a listed type without subscribers is published without deliveries | Such a row was written by a newer image: an image rolled back keeps it for the next roll-out, and the age monitor pages meanwhile |
| F1-C20 | `outbox_messages` and `processed_events` have no row-level security | The relay and the purge sweep every tenant of a home (F1-C6 leaves cross-tenant sweeps under RLS to S02); the rows hold ids and codes only and the application reaches them only through `core/events` |
| F1-C21 | The relay opens a producer span per event as the child of the stored trace context, linked to its own run; the delivery's consumer span is its child | §14 rule 13 asks for trace context across outbox events; the span shows how long the event waited in the outbox |
| F1-C22 | A slice is one `FeatureModule`: static `name`, `models`, `events`, `production_checks`, and `build(CoreServices)`, an async context manager yielding `FeatureParts` (HTTP and WS routers, task handlers, subscriptions, loops, probes); every role builds every slice. *Amended 2026-10-13 (F1 audit OD-2): `contract_slice` removed* | Dependencies are injected, not imported; a slice opens and closes its clients with the process, so its start hooks always run (draft lesson); every role registers every task (§14 rule 9) |
| F1-C23 | The task system makes the brokers and the sender before any handler; composition registers the handlers after the slices are built (`TaskSystem.register`), and the outbox lists the event classes (`EventTypes`) before the subscriptions exist | Slices build their handlers and subscriptions with the sender and the outbox, so both must exist first |
| F1-C24 | The process binds its sockets itself and runs uvicorn without its signal capture; one stop sequence drains the public server first and the ops server last. HTTP through h11; no WebSocket library until S05 chooses one with its frame protocol; the public server keeps an idle connection 75 s, longer than the edge keeps its idle upstream connections (NGINX: 60 s by default, F4) | uvicorn would stop both servers at once on SIGTERM and exits the process on a busy port; httptools is not added without a measurement that needs it; with uvicorn's 5 s the server would close connections the edge is about to reuse (502) |
| F1-C25 | Readiness probes the dependencies only while the process is ready; a home's probe runs one statement through the process's own pool and is `down` for a home the start check closed | Before readiness the clients do not exist and after it they close; a closed home answers but takes no transaction |
| F1-C26 | Work that ends by itself — a server or a worker task — stops the process with exit code 1 | A process that looks alive but serves nothing is worse than a restart |
| F1-C27 | Scheduler loops run at start and then once per interval, never as a backlog, each iteration within 10 s; the daily purge therefore also runs at each scheduler start until F6 moves periodic jobs to `schedule_runs`. Loop metric names are the draft's | The purge is idempotent and skips while one runs (tick marker); the draft's loop alert rules carry over to F5 |
| F1-C28 | `shosai migrate` has `upgrade` and `current`, no downgrade | Migrations only expand the schema and a release is rolled back by its previous image (§13.3, F1-D7); every downgrade still runs in every test run |
| F1-C29 | The route snapshot holds the public routes of `api` and `ws` separately (`tests/composition/public_routes.json`); the D1 gate checks the composed apps. *Amended 2026-10-13 (F1 audit OD-2): it checks the `native` routes the apps serve, whatever the slice, and records the native routes not served yet* | A route change is a reviewed diff in the same commit (§14 rule 12); a slice joins the gate the moment composition lists it |
| F1-C30 | The stop fits a 30 s container grace period: drain 20 s, ops server 2 s, span export 5 s; F4 sets `stop_grace_period: 30s` | The draft's grace period and drain, kept; a test keeps the sum under the grace period |

## 3. Design

### 3.1 Layout

```text
backend/
  pyproject.toml, uv.lock     uv project; Ruff, mypy, pytest, coverage, import-linter
  LICENSE                     copy of the root licence (PEP 639 forbids paths outside the project)
  README.md                   roles, local run, tests, gates, how a slice is added
  src/shosai/
    migrations/               env.py, revision template, versions/ (exempt from the length limit);
                              package data, so a process finds the history in an installed image
    core/
      kernel/                 framework-free: Home, TenancyScope, AppError family, UUIDv7 ids, clock
      runtime/                uvicorn servers stopped in order, scheduled loops, the stop signal
      config/                 settings sections, production gate
      observability/          structlog, redaction, log context, tracer provider, metrics registry, loop lag
      web/                    ASGI middlewares, error envelope, HTTP metrics, route templates, rate-limit dependency, health router
      db/                     engines per home, transactions with tenancy scope, model base, home identity, pool metrics
      kv/                     Valkey client, distributed locks, GCRA limiter
      cache/                  cache port and Redis adapter
      storage/                object-storage port and the S3 adapter of the one bucket (ADR 0014)
      tasks/                  brokers per queue, task declaration, middlewares, leases, dead letter
      events/                 domain-event base, outbox writer, subscriptions, relay, delivery
      crypto/                 Fernet key ring
      i18n/                   the 16 locales, Accept-Language
      health/                 probe protocol, readiness aggregation
      features.py             FeatureModule, CoreServices, FeatureParts: what a slice contributes
    features/                 one package per slice (none in F1); its public surface is contracts.py
    composition/              the explicit feature list, telemetry, the platform per process,
                              the roles, the scheduler's core loops, the process life, migrate
    entrypoints/              CLI: shosai api | ws | workers --queue Q | scheduler | migrate …
  tests/
    harness/                  slot claim, guards, catalog fingerprint, test settings (ADR 0009)
    model_facing/             registry and the English check
    …                         mirrors src/shosai
```

A feature exposes one `FeatureModule`: HTTP and WS routers, task declarations, event subscriptions, scheduler loops, health probes, model metadata. Composition lists the features explicitly and wires them per role.

### 3.2 Boundaries

import-linter contracts in `pyproject.toml`, enforced by CI (§14 rule 12):

| Contract | Type | Rule |
|---|---|---|
| Layers | `layers`, exhaustive | `entrypoints` → `composition` → `features` → `core`; a new top-level package must join a layer |
| Features meet through contracts | `independence` over `shosai.features.*`, ignoring imports of `shosai.features.*.contracts` | A feature imports another only through its `contracts` module |
| Pure kernel | `forbidden` | `core.kernel` imports no FastAPI, Starlette, SQLAlchemy, redis, TaskIQ, aiobotocore, HTTPX, structlog or OpenTelemetry |

With no features yet, a test runs `lint-imports` on a fixture tree with two features, one importing the other's internals, and asserts the violation is reported. Inside a slice the layering (`channels` → `application` → `domain`, `infrastructure` implementing ports) is the slice's own contract; the backend README gives the template.

### 3.3 Configuration

- `pydantic-settings`, one `Settings` made of typed sections, `env_file` off. Locally: `uv run --env-file ../.env shosai api`.
- Names: F3's `HOME_RU_*` and `HOME_EU_*` (database, migration database), `S3_*` for the one bucket (ADR 0014; replaces `HOME_<H>_S3_*` in step 5), `VALKEY_URL`, `REDIS_CACHE_URL`; the standard `OTEL_*` variables; the draft's `FERNET_KEY` and `FERNET_KEYS_PREVIOUS`; the rest named in step 2. Every variable is documented in `.env.example` section 2 with its purpose; local values only.
- `ENVIRONMENT`: `development`, `staging` or `production`. Tests build their settings from `TEST_*` values (ADR 0009).
- Production gate: refuses to start when API docs are on, the trusted-proxy list is empty, the crypto key is missing, `LOG_LEVEL` is `DEBUG` (§16.7), the storage endpoint is not `https`, Valkey is not reached over TLS (`rediss://`, F1-D12), or a home's database address lacks `sslmode=verify-full` (ADR 0013, step 4). A missing home database or bucket, a missing `ENVIRONMENT` and a CORS wildcard are refused in every environment when the settings load. The message names the setting, never its value. A slice adds its own checks through the gate (S03: billing dev mode).
- Lists are comma-separated variables, never JSON. The migration address is optional: only `shosai migrate` needs it, so the long-running roles do not hold the schema owner's password.
- Secrets are `SecretStr`; the logging pipeline never renders them.

### 3.4 Logging, context, telemetry

- structlog renders one JSON line per event on stdout; standard-library loggers (uvicorn, SQLAlchemy, TaskIQ, botocore) go through the same renderer. Messages are Russian, keys English.
- Context from contextvars on every line: `role`, `request_id`, `trace_id`, `span_id`, and where known `home`, `org_id`, `user_id`, `session_id`, task name and id (§16.2).
- Redaction by key (exact names and suffixes, as in the draft); request bodies, headers and query strings are never logged (§16.8).
- One access line per request: method, route template, status, duration.
- Traces: our own `TracerProvider` with a bounded batch queue and a short export timeout; no exporter when `OTEL_EXPORTER_OTLP_ENDPOINT` is unset; dropped spans are counted (§16.1). FastAPI's native tracing with `auto_configure`, `metrics` and `logs` off; instrumentation of HTTPX, redis and TaskIQ. SQLAlchemy statements get our own client spans (`core/db/tracing.py`, step 4): the official instrumentor patches `create_engine` globally and its per-engine class is untyped.
- Metrics: HTTP RED metrics recorded by the request boundary from the route FastAPI has already matched, under the instrumentator's contract (ADR 0012); `prometheus_client` for the rest: event-loop lag (a histogram, so a spike between two scrapes is seen), pool occupancy per home, task and outbox metrics, telemetry drops. One registry per process, passed in; labels stay bounded (§16.7).
- Logs leave through a bounded queue to a writer thread, rendered in the caller's thread; a full queue drops the line and counts it (§16.1).
- The fastapi skill prefers FastAPI's native metrics and logs; §16.1 keeps the HTTP metrics under the instrumentator's names and labels (ADR 0012) and logs through structlog, so those two are off.

### 3.5 HTTP shell and errors

- An app factory per role; no module-level app.
- Pure ASGI middlewares, outermost first: request id (ADR 0008), access log and log context, security headers (HSTS on HTTPS, `nosniff`, `Referrer-Policy`). CORS only for an explicit allowlist, empty by default.
- Proxy trust through uvicorn's `proxy_headers` with `forwarded_allow_ips` from `TRUSTED_PROXY_ADDRESSES`.
- Errors per ADR 0008: `AppError` in the kernel; handlers for it, `HTTPException`, validation, unknown path, method not allowed and unhandled exceptions; `ErrorResponse` in OpenAPI. API docs off in production.
- Dependencies are typed `Annotated` aliases defined once (draft lesson: two copies of `get_db` split test overrides).

### 3.6 Home-aware data access and RLS groundwork

- `Home` is `ru` or `eu`; the directory and platform data name `Home.EU` explicitly (ADR 0010).
- `HomeDatabases`: exactly one `AsyncEngine` per home per process (§14 rule 2). Pool size by role (api 10, workers 5, ws and scheduler 2; §4.3), `max_overflow=0`, pool wait 2 s, `pool_recycle=600`, no pre-ping, psycopg with `prepare_threshold=None` (ADR 0013), connect timeout 5 s, TCP keepalives, `application_name=shosai-<role>`, bound values hidden from exceptions and logs.
- `TenancyScope(home, user_id, org_id)`. S01 builds it from the access token (§4.1 rule 3); a task builds it from its payload.
- `HomeTransactions.begin(scope, read_only=False)` opens a session on the scope's home and starts a transaction whose first statement is one `SELECT set_config(...)` setting `statement_timeout` (API 10 s, workers 60 s), `app.user_id`, `app.org_id` and read-only mode with transaction scope. It commits on exit and rolls back on error. No request-wide session: a handler commits before it returns and calls external services between transactions (§14 rule 1).
- Round trips per transaction: `BEGIN`, scope, the statements, `COMMIT`. A test counts them; at 45 ms to the Russian home this is §3's "4 × 45 ms" budget.
- Every home database has a one-row `home_identity` written by the first migration. `HomeGate` checks each home at start and before the first transaction of an unverified home (F1-D7, F1-D8): another home's database or a schema behind the code stops the start; a newer schema passes; a home out of reach is refused with 503 `home_unavailable` until it is verified.
- A transaction that gets no connection (pool wait over, connection refused) is 503 `home_unavailable` with `Retry-After` for that home only (§13.2), counted in `shosai_db_unavailable_total{home, reason}`; pool occupancy is read at scrape time per home.
- RLS groundwork: SQL functions `app_user_id()` and `app_org_id()` reading the transaction settings; a migration helper that grants a table to the application role explicitly (no default privileges, so a new table is closed until granted); a helper that enables the standard company policy, used by S02. Tests under `shosai_app` through PgBouncer prove that a policy hides foreign rows and that `SET LOCAL` values do not reach the next transaction on the same server connection.

### 3.7 Migrations

- One script directory `src/shosai/migrations/` (package data), one linear history, migrator role over the direct connection (`HOME_<H>_MIGRATION_DATABASE_URL`), a session advisory lock per home and `lock_timeout = 5s`. The runner is `core/db/migrations.py`; `uv run alembic revision` uses `[tool.alembic]` in `pyproject.toml` only to write a revision.
- A revision receives `MigrationScope(home, application_role)`; `runs_in(applies_to)` skips it in other homes; the application role's name comes from the home's application address, so grants need no extra setting.
- `shosai migrate upgrade` applies the history to the RU home, then the EU home; it stops at the first failure and prints each home's revision.
- `applies_to` per revision (ADR 0010); constraint naming convention; UUIDv7 keys for high-volume tables (§8.2); expand-only changes (§17); every revision has a downgrade, run by every test session (ADR 0009).
- A test compares the migrated schema with the models (`compare_metadata` is empty), so models and migrations cannot drift.

### 3.8 Valkey, cache, object storage

- **Valkey:** one redis-py client with a bounded pool (64) per process, no client-side retries; deadlines per call class with `asyncio.timeout` (enqueue 50 ms, locks 50 ms, rate limits 50 ms; §4.3); blocking reads ≤ 2 s; commands traced with their arguments replaced by `?`.
- **Locks:** token plus TTL, released and extended by compare-and-delete and compare-and-expire in Lua; every call states fail-closed or fail-open.
- **Rate limits:** ADR 0011. A route declares `RateLimit(name, rate, burst, subject)`.
- **Cache:** a port with `get`, `get_many`, `set` with TTL, `delete`; keys `CacheKey(namespace, name)` with the shape's version in the namespace; 20 ms per call and TTL jitter (F1-C7); a failure is a miss, logged at most once per 10 s and counted. Access rights are never cached (§7).
- **Object storage:** one aiobotocore client per process for the one bucket of both homes (ADR 0014, ADR 0015), with path addressing, connect 2 s and read 20 s timeouts, standard retries with 3 attempts (§14 rule 8), checksums only where S3 requires them. Operations: put, streamed get, head, delete, delete many, list a prefix, presigned get and put (15 min, §4.3; an upload link is signed for one content type and length, a download link may pin the content type), multipart create, presign part, list parts (F1-C10), complete, abort. No database session is held across a storage call.

### 3.9 Tasks

- One `ValkeyStreamBroker` per queue (`critical`, `default`, `bulk`, `meeting`), our own subclass of TaskIQ's `AsyncBroker` over the process's Valkey client (ADR 0016): stream `shosai:tasks:<queue>` holding only unfinished tasks, group `shosai` reading from `0`, at most 500 000 entries, lease 120 s renewed every 15 s, recovery every 5 s (§4.3).
- Every process can enqueue to every queue within 50 ms, or gets `TaskQueueUnavailableError` (503 `queue_unavailable`); a worker process consumes one queue with TaskIQ's receiver, one message at a time, acknowledging after the middlewares.
- A task is a `TaskDeclaration(name, queue, payload, deadline, retry, kind)`: a stable explicit name `slice.task`; one frozen Pydantic payload that ignores unknown fields; a home-scoped payload carries `home`; new fields are optional (§14 rule 9). A `TaskHandler` binds it to the function composition builds with the process's resources; `build_task_system` registers every handler in every role.
- Middlewares: trace context in the labels and a consumer span per run (F1-C13); the lifecycle — log fields, one line and metrics per run, the settlement: acknowledge, retry later (F1-C11), dead letter (F1-C12), leave pending when interrupted. Unknown or unparseable messages are dead-lettered and counted before the receiver sees them.
- Tick markers so a periodic enqueue never overlaps itself; a failed or abandoned tick is dropped, not retried or dead-lettered.
- `QueueMonitor` sets the depth, oldest-task and dead-letter gauges in one round trip; step 8 runs it in the scheduler.

### 3.10 Events

- `DomainEvent`: a frozen Pydantic model with `event_type` (`slice.object.happened`) and `version`. Fields are ids, numbers, flags, timestamps, enums or `EventCode` strings (`^[a-z0-9_.:-]{1,64}$`), or tuples and frozensets of them; the class is checked when it is defined, so an email or a name cannot enter an event (§12), and tests prove each refused kind.
- `outbox_messages` and `processed_events` in both homes (§8.1), without row-level security (F1-C20). `outbox.add(session, event)` writes into the caller's transaction and stores the transaction's account and company (F1-C17), the trace context and the request id.
- Subscriptions are declared by features: consumer name, event type, queue, deadline, handler. Composition lists events and subscriptions in an `EventCatalog`, which rejects a type listed twice, a consumer subscribed twice and a subscription to an unlisted event.
- Relay, a `critical` task per home: claim up to 100 rows with a 30 s lease (`FOR UPDATE SKIP LOCKED`) and commit; enqueue one delivery task per subscriber outside any transaction (§14 rule 1), inside a producer span continuing the stored trace (F1-C21); mark the rows published in a second transaction. A failed enqueue holds the row back with backoff `min(2^attempts, 300 s)`; a type the image does not list is held back the same way (F1-C19).
- Delivery: one task per subscription, `events.<consumer>`, carrying the event and its scope (F1-C18). In the event's home and scope, one transaction inserts `processed_events (consumer, event_id)` with `ON CONFLICT DO NOTHING`, runs the handler only for a new row, and commits both together. An unknown consumer is an unknown task: dead-lettered and counted by the broker (step 6).
- Scheduler ticks: relay every 5 s per home (§12: 100 per 5 s); purge daily (F1-C5). Metrics: pending rows and the age of the oldest one per home (§16.4 monitor "outbox events older than 5 min").

### 3.11 Process roles and health

- One console script `shosai`. One process per container, one uvloop event loop.

| Role | Serves | Runs |
|---|---|---|
| `api` | public app on `HTTP_PORT`: feature routers and `GET /v1/health` → `200 {"status":"ok"}` | — |
| `ws` | public WS app: feature WS routers and `GET /v1/health` | — |
| `workers --queue Q` | — | the receiver of one queue |
| `scheduler` | — | the loop runner: outbox relay and purge in F1, the `schedule_runs` walker from F6 |
| `migrate …` | — | one-shot Alembic commands for both homes |

- Every long-running role also serves on `OPS_PORT` (never proxied by the edge): `GET /livez`, `GET /readyz` and `GET /metrics`.
- Readiness is 200 after start and 503 while starting or draining. The body reports each dependency (`homes.ru`, `homes.eu`, `valkey`, `cache`, `storage`) as `ok` or `down`, each checked with a 2 s timeout. Dependencies do not fail readiness (F1-C2); they are alerted through metrics.
- Start: settings and gate → logging and telemetry → engines, home identity and head check → Valkey, cache, storage → brokers → the role. A failed step exits non-zero with a log line naming it.
- Stop on `SIGTERM`: readiness 503 → stop accepting work → drain (in-flight requests; running tasks within their deadline, the rest are redelivered after the lease; loops stop) → close clients → dispose engines → flush telemetry. Each step logs its failures; none is suppressed.
- Loops: a failing iteration is logged with its stack and the loop continues; each success updates `shosai_loop_last_success_timestamp{loop}` (spec 013).

### 3.12 Model-facing English test

`tests/model_facing/registry.py` lists the sources of model-facing text, each with its owner and a callable that returns the objects. The collector walks strings in mappings and sequences, enum values, Pydantic JSON schemas and tool schemas. Allowed non-English literals (language endonyms) are declared per entry. A string fails if it contains a letter outside the Latin script. Self-tests prove that a Russian instruction fails and a declared endonym passes. The registry starts empty.

### 3.13 CI

The backend job replaces its single PostgreSQL service with the `compose.dev.yaml` services F1 needs (both homes, both PgBouncers, Valkey, Redis cache, S3), sets the `TEST_*` variables, and runs `uv sync --locked`, Ruff format and lint, mypy strict, `lint-imports`, `pytest --cov`, python-doctor 100 and pip-audit. The contracts harness joins as a path dependency for the route checks of step 8.

### 3.14 Not in F1

Token and directory (S01); access policy, RLS policies, audit (S02); provider port, email, `schedule_runs` (F6); Qdrant client (S07); WS frames, drain protocol, 1013 (S05); Dockerfile, NGINX, ulimits, release (F4); collector and Grafana stack (F5); the limits on each route (their slices).

## 4. Steps

Every step leaves the project working: its tests pass, python-doctor prints 100, mypy strict, Ruff and `lint-imports` are clean, and after «Принято» it is committed, pushed and CI on `main` is green. Every step loads `fastapi` and `python-doctor`, and the four Docker skills when it starts the local environment.

| Step | Content | Skills | Done when |
|---|---|---|---|
| 1 | **Skeleton and test harness.** `uv` project on Python 3.14 with only this step's dependencies; Ruff (with `ASYNC`, `S`, `ANN`), mypy strict (pydantic plugin, 3.14), pytest and coverage settings; `LICENSE` copy; the layout of §3.1 with empty `features`; import-linter contracts of §3.2 with the fixture test; harness of ADR 0009 for the databases (settings, guards, two-home slot claim, catalog fingerprint); model-facing registry and test; CI backend job on the compose services; `.env.example` `TEST_*` section and `development.md` test-slot paragraph.<br>Done: 71 tests; four concurrent runs held four different slots in every round; the end-of-run check fails a run that leaves a table; a claim also restores extensions, default privileges, schema and database rights and settings (ADR 0009 amended); docstrings are English and checked; asyncpg and Pydantic are dev dependencies until steps 2 and 4 need them at runtime | fastapi, python-doctor, Docker ×4 | Gates pass locally; two concurrent runs hold different slots; the guard refuses `shosai` and a non-loopback host; a leftover table is detected and cleaned; CI backend job green |
| 2 | **Configuration and observability.** Settings and production gate; `.env.example` section 2 complete; structlog pipeline with redaction and context; tracer provider with bounded export and drop counter; metrics registry and loop-lag gauge; crypto key ring; locales and Accept-Language<br>Done: `core/config` (sections from an explicit mapping, every problem by name, gate with slice checks), `core/observability` (JSON lines through a bounded queue, redaction, `log_context`, bounded span processor counting drops, registry, loop-lag histogram), `core/crypto`, `core/i18n`; 99 new tests (170 in all) incl. Hypothesis properties; a test keeps `.env.example` section 2 equal to the settings | fastapi, python-doctor, observability | A `.env` in the working directory is ignored; each gate case refuses start and names the setting; no secret value appears in any log line (property test); log lines carry `trace_id` inside a span; key rotation decrypts old ciphertexts |
| 3 | **HTTP shell.** API app factory without features; request-id, access-log and security-header middlewares; error envelope and every handler (ADR 0008); `ErrorResponse` in OpenAPI; native tracing and the instrumentator; proxy trust; `GET /v1/health`<br>Done: `core/kernel/errors` (`AppError` checks code, status and params), `core/web` (one pure-ASGI request boundary for the id, log context, common headers, the access line and the last-resort 500; handlers for every error path; `ErrorResponse` as every operation's `default` response; native server spans without operation spans; instrumentator; CORS allowlist; `forwarded_allow_ips`; `GET /v1/health`); a sampler drops raw paths, queries and client addresses from spans; HTTPX and `uvicorn.access` loggers quieted; D1 harness as a dev dependency, F1 routes compatible; 83 new tests (253 in all). Measured: the instrumentator re-matches the route table per request, +0.2 ms on the first and +0.54 ms on the 600th route — open item F1-O1 | fastapi, python-doctor, api-design | Every error path (domain, `HTTPException`, unknown `/v1` path, 405, 422, 500) returns the envelope with `X-Request-ID`; 422 never echoes input; one log line per 500; the D1 harness passes for F1's route |
| 3a | **HTTP metrics in the request boundary** (F1-D5, ADR 0012): `core/web/http_metrics.py` and `core/web/route_templates.py` on prometheus-client; the instrumentator removed; §16.1, §16.7, §18.2 updated<br>Done: the five metrics keep the instrumentator's names, help texts, labels and buckets; the template is looked up in maps built at start through `iter_route_contexts`, never matched again; prefixes, nested routers, mounts and Starlette routes resolve; label values come from closed sets; 64 new tests (317 in all). Measured on 600 routes: 258 µs of CPU per request with the instrumentator, 7 µs with the boundary | fastapi, python-doctor | The contract test pins the five metrics; a property test finds no label value outside the closed sets; each request is recorded once, cancellation included; the shell adds no `matches()` call to FastAPI's routing; every layout resolves to the template FastAPI traces |
| 4 | **Home-aware data access, migrations, RLS groundwork.** §3.6 and §3.7; harness extended with upgrade, per-test truncation, downgrade<br>Done: the owner decided F1-D6…D8 (ADR 0013, ADR 0010 amended); `core/db` (engines per home with role limits, `HomeTransactions` with the scope statement, `HomeGate`, 503 `home_unavailable`, pool and home-state metrics, statement spans, model base with home scope, migration runner and helpers, `home_identity`), first revision with `app_user_id()` / `app_org_id()`, `composition/metadata.py`; database addresses are libpq URLs and production requires `sslmode=verify-full`; harness on psycopg, migrates the slot up and down, `homes` fixture empties tables; 75 new tests (392 in all). Measured through a counting proxy: a scoped read is 4 round trips, 3 statements 6; 3 processes × 60 concurrent transactions through PgBouncer see only their own scope; no prepared statement remains on a server | fastapi, python-doctor, data-storage, Docker ×4 | A row written through the EU home is invisible through the RU home and the reverse; `SET LOCAL` does not leak across PgBouncer transactions; a policy hides foreign rows under `shosai_app`; swapped home URLs fail at start; a home behind head fails at start; `compare_metadata` is empty; round trips per transaction counted |
| 5 | **Valkey, cache, object storage.** Clients, locks, GCRA limiter (ADR 0011), cache port, S3 port for the one bucket with settings `S3_*` replacing `HOME_<H>_S3_*` in the settings, the gate, `.env.example` and the tests (ADR 0014), readiness probes; F3's local store keeps one bucket (`compose.dev.yaml`, `development.md`, a note in ADR 0001); harness extended with slot databases in Valkey and Redis and the `tests/slot-<N>/` prefix<br>Done: the owner decided F1-D10…D12 (ADR 0015, ADR 0009 item 2 amended, Valkey over TLS in production); `core/kv` (one client with a bounded pool and no client retries, key layout, locks with a per-call outage policy, GCRA limiter in one Lua script on Valkey's clock), `core/web/rate_limit.py` (429 `rate_limited` with `Retry-After`, any subject, draft `detail`), `core/cache` (port, Redis adapter, 20 ms, TTL jitter), `core/storage` (ports for objects and multipart uploads, aiobotocore adapters under an optional root, errors, client spans without keys), `core/health` (probes and their aggregation), `OutageLog`; settings `S3_*` and the gate; harness with `TEST_VALKEY_URL`, `TEST_REDIS_CACHE_URL`, `TEST_S3_*`, fixtures `valkey`, `redis_cache`, `bucket` and the end-of-run check; local store and CI on one bucket; 119 new tests (511 in all). Verified on SeaweedFS: a presigned upload refuses another length or content type, a presigned download pins the type, a failing bucket is asked exactly 3 times | fastapi, python-doctor, caching, blob-store, resilience-failure, Docker ×4 | Limiter property tests and fail-open under a stopped Valkey; lock fail-closed and fail-open cases; presigned multipart round trip on SeaweedFS; a cache outage is a miss; no keys or objects left |
| 6 | **Tasks.** Brokers per queue, task declaration, middlewares, leases, dead letter with redaction, retries with backoff, unknown-task handling, tick markers<br>Done: the owner decided F1-D13 (ADR 0016, §18.2); `core/tasks` (queues and profiles, declarations, payloads with `TaskSecret`, timing and backoff, Lua scripts, `TaskStream`, `ValkeyStreamBroker`, deliveries and settlements, settler, dead-letter entries, lifecycle and tracing middlewares, sender with ticks, tick markers, `build_task_system`, `consume_queue`, `QueueMonitor`); TaskIQ's duplicate exception line and its INFO and DEBUG lines (task arguments) kept out of the logs; `log_context` gains `bind_log_fields` and `bound_request_id`; the probe-table fixture is shared by the database and task tests; 116 new tests (627 in all). Found by the tests: TaskIQ's `WHEN_EXECUTED` acknowledges before the middlewares decide, so the receiver acknowledges `WHEN_SAVED` | fastapi, python-doctor, messaging-streaming, task-scheduling, Docker ×4 | A task runs in the home named by its payload; a long task is not redelivered while its lease is extended; the fifth failed delivery lands in the dead letter with redacted fields; an unknown task is dead-lettered and counted; trace context crosses enqueue → execution |
| 7 | **Events.** Outbox and processed-events tables, writer, subscriptions, relay and delivery tasks, purge, the event-field rule, metrics<br>Done: `core/events` (`DomainEvent` checked at class definition, `EventCatalog`, `EventOutbox`, `EventSubscription` and the delivery task per consumer, `OutboxRelay` with lease, backoff and producer spans, `OutboxPurge`, `OutboxMonitor`, `EventMetrics`, `event_task_handlers`), revision `959dbda6a28e` for both homes; `HomeTransactions` records the scope in the session (`transaction_info`); `build_task_system` binds handlers to the process's sender; `LogFields` gains `event_id`; design choices F1-C17…C21; 78 new tests (705 in all), `core/events` covered 100%. Found by self-review: PostgreSQL's `power()` overflows past 2^1023, so an event held back for ≈ 3.5 days would have failed the marks of its whole pass; the exponent is capped | fastapi, python-doctor, messaging-streaming, Docker ×4 | An event committed with its effect reaches each subscriber once; a rolled-back effect emits nothing; a redelivered event does not rerun the handler; a failed enqueue is retried with backoff; each home relays independently; an event with a free-text field is rejected |
| 8 | **Process roles and health.** CLI, ops server, `api`, `ws`, `workers`, `scheduler`, `migrate`; start sequence and checks; graceful stop; loop runner with relay and purge loops and heartbeats; route snapshot and the D1 harness gate; backend README; `development.md` "Run the backend"; STATUS `done`. The start uses `HomeGate.verify_at_start()`: `HomeMisconfiguredError` exits non-zero, an unreachable home is logged and the role starts (F1-D8)<br>Done: design choices F1-C22…C30; `core/features.py` (`FeatureModule`, `CoreServices`, `FeatureParts`), `core/runtime` (servers, loops with heartbeats, signals), `core/health/readiness.py` and the home probe, `core/web/ops.py`; `composition` (features, telemetry, platform in named steps, roles, core loops, process life, migrate) and `entrypoints/cli.py` with the console script and uvloop 0.23.0 (§18.2); settings `BIND_HOST`, `HTTP_PORT`, `OPS_PORT`; `TaskSystem.register` and `EventTypes`; route snapshot and D1 gate over the composed apps; fixed: Alembic could not name a scoped step in its log line (step 4). 71 new tests (776 in all), incl. each role as a subprocess against F3 and a Russian home out of reach at start, back, then cut. Measured locally: `api` ready 0.17 s after its first line, SIGTERM to exit 0.36 s | fastapi, python-doctor, observability, Docker ×4 | All four roles start against F3 and answer `/livez` and `/readyz` (a test starts each as a subprocess); `SIGTERM` drains each cleanly; with the RU database stopped, readiness stays 200 and reports `homes.ru: down`; the prompt's definition of done holds; CI green |

## 5. Risks

| Risk | Handling |
|---|---|
| A dependency lacks Python 3.14 wheels | Found by `uv sync` in step 1; building from source in CI is the fallback, a version change needs the user |
| The `independence` contract misbehaves with zero features | Step 1's fixture test shows it before any slice relies on it |
| A FastAPI upgrade changes what routing leaves in the scope | `tests/core/web/test_route_templates.py`, including agreement with FastAPI's own `http.route`, fails CI before the upgrade reaches production (ADR 0012) |
| SQLAlchemy 2.1 behind PgBouncer reuses statement names under concurrency | Resolved in step 4: psycopg prepares nothing (ADR 0013); concurrent transactions of three processes through PgBouncer are tested |
| TaskIQ changes the receiver's acknowledgement order or the decorated-task class between versions | The broker uses only TaskIQ's public interface; the worker tests run the real receiver against Valkey on every run, so an upgrade that breaks settlement fails CI (ADR 0016) |
| SeaweedFS differs from the providers' S3 | Tests use only operations ADR 0001 verified; the ADR's revisit trigger applies |
