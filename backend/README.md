# Whisperer backend

One modular monolith, one image, four process roles (`api`, `ws`, `workers`, `scheduler`), built feature-first: `core/`, `features/<slice>/`, `composition/`, `entrypoints/` under `src/whisperer/` ([target architecture](../docs/design/ARCHITECTURE.md) §5). The package is built step by step by [F1](../docs/plan/packages/F1-backend-foundation.md); this file grows with it.

## Boundaries

import-linter contracts in `pyproject.toml` (`uv run lint-imports`):

| Contract | Rule |
|---|---|
| Layers | `entrypoints` → `composition` → `features` → `core`; never upward |
| Features meet through contracts | a slice imports another slice only through its `contracts` module |
| Pure kernel | `core.kernel` imports no framework, driver, client or telemetry library |

## Configuration

`core/config` reads the settings once per process from environment variables and passes them in; nothing reads a `.env` file or keeps a cached global. Every variable is documented with its purpose in section 2 of [`.env.example`](../.env.example), and a test keeps that section in step with the settings sections. Locally uv passes the file: `uv run --env-file ../.env …`.

- `load_settings(os.environ)` reports every invalid or missing variable at once, by name, never by value.
- `ENVIRONMENT` is required. With `production`, `enforce_production_gate` refuses to start when the API docs are on, `TRUSTED_PROXY_ADDRESSES` or `FERNET_KEY` is missing, `LOG_LEVEL` is `DEBUG` or a home's storage endpoint is not `https`. A slice adds its own checks through `extra_checks`.
- A slice declares its own section as a subclass of `SettingsSection` and documents its variables in section 2.

## Logs, traces, metrics

`core/observability` follows target architecture §16.

- Log with `structlog.stdlib.get_logger(__name__)`: the message in Russian, fields as English keyword arguments. Standard-library loggers go through the same renderer: one JSON line per event on stdout with `timestamp`, `level`, `logger`, `role`, `service`, and inside a span `trace_id` and `span_id`.
- `log_context(request_id=…, home=…, org_id=…, user_id=…, session_id=…, task_name=…, task_id=…)` adds the ids of a unit of work to every line inside the block.
- Values under sensitive keys, `SecretStr` values and passwords inside URLs are replaced by `***`; never log request bodies, headers, query strings, personal data or meeting text.
- Lines and spans leave through bounded queues and never block the event loop; what does not fit is dropped and counted in `whisperer_telemetry_dropped_total{signal, reason}`. Without `OTEL_EXPORTER_OTLP_ENDPOINT` spans are recorded for the log correlation but not exported.
- Metrics register in the process registry passed in (`build_metrics_registry`), never in the global one; labels stay bounded (§16.7). `watch_event_loop_lag` feeds `whisperer_event_loop_lag_seconds`.

## Tests

Tests that touch the databases need the local environment ([docs/development.md](../docs/development.md)); all tests read only `TEST_*` variables ([ADR 0009](../docs/adr/0009-test-databases-claimed-by-advisory-lock.md)), listed with local values in section 3 of [`.env.example`](../.env.example).

```bash
../scripts/local-env.sh up
cp -n ../.env.example ../.env      # once
uv run --env-file ../.env pytest
```

- The session fixture `run_slot` claims a free prepared slot `whisperer_test_<N>` in both homes with an advisory lock, so parallel runs never share one, and gives a direct migration-role connection per home. A crashed run's lock is released with its connections. The pytest summary names the slot.
- The harness refuses to start if a host is not loopback, a database name is not `whisperer_test`, the claimed database is not a prepared test database, or a `TEST_` URL equals a runtime URL.
- On claim the harness returns the slot to the state F3 prepares — it drops a crashed run's objects and the extensions the migration role created, and restores default privileges, rights on the `public` schema and on the database, and database settings. At the end it fails the run, naming the objects, if the catalog of either home differs.

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
