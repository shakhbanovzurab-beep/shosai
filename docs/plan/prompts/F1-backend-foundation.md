# F1 — Backend foundation

Follow the common protocol in `docs/plan/prompts/README.md`. Load the `fastapi` skill before reading the draft or designing anything.

**This package is multi-session.** Work in the session mode described in `docs/plan/prompts/README.md`; the package plan is `docs/plan/packages/F1-backend-foundation.md`. A split that fits the work below — adjust it in the plan if the design needs another order:

1. Project skeleton: `uv` project, `pyproject.toml` with Ruff, mypy strict and import-linter, layout of §5, the license copy, test infrastructure against F3 (item 12), CI backend job green on an empty project.
2. Configuration, structured logging, telemetry hooks and the error envelope (items 3, ADR on the envelope).
3. Home-aware data access, Alembic for both homes and RLS groundwork (items 4, 7, 8).
4. Valkey, Redis cache and the S3 client of the one bucket (item 5, ADR 0014).
5. Outbox, processed events and the relay contract (item 6).
6. The four process roles, health endpoints, the model-facing-English test and the import-linter contracts between features (items 2, 9, 10, 11).

## Goal

A backend project in `backend/` that every slice builds on, with no feature code yet. After this package the backend CI job runs and is green.

## Read first

- CLAUDE.md in full; target architecture §4.2, §5, §6, §7, §8.2, §12, §14, §15, §16, §18.
- How the draft solves the same concerns (`/root/whisperer/backend/src/meetassist/core/`, `composition/`, `entrypoints/`), for lessons only.

## Work

1. `uv` project on Python 3.14 with the stack from CLAUDE.md and target architecture §18, latest stable, pinned in `uv.lock`. Dev dependencies as listed in CLAUDE.md "CI". mypy strict and Ruff configured in `pyproject.toml`.
2. Layout per target architecture §5: `core/`, `features/`, `composition/`, `entrypoints/`, with the four process roles `api`, `ws`, `workers`, `scheduler` started from one image.
3. `core`: configuration through `pydantic-settings` with `.env.example` documenting every variable; structured logging with structlog; OpenTelemetry tracing and metrics that never block a request; the error envelope with `request_id`; exactly one pool per process per database.
4. **Home-aware data access**: a session factory that opens the database of the home named by the access token or the task payload (target architecture §4.1, §6). It must work with two local databases standing in for the RU and EU homes (F3).
5. Valkey (tasks, locks, transcript queue), Redis LRU cache, and the S3 client of the one bucket in Russia (ADR 0014), behind interfaces that slices receive through dependency injection.
6. Outbox and processed-events tables and the relay contract (target architecture §12), without any feature events yet.
7. Row-level security groundwork: `SET LOCAL app.org_id` and `app.user_id` per transaction; a separate role for migrations.
8. Alembic set up to apply the same migrations to both homes.
9. Health endpoints under `/v1`, matching the draft's paths where D1 lists them as client-facing.
10. The model-facing-English test from CLAUDE.md "Prompts", with an empty registry ready for slices.
11. import-linter contracts that make `features/*` depend on each other only through their `contracts` modules.
12. Test infrastructure: tests read only `TEST_DATABASE_URL`, refuse any non-test database, claim a free prepared test database when run in parallel, and leave data and schema unchanged afterwards.

## Decisions to record as ADRs, confirmed by the user

- The shape of the error envelope (CLAUDE.md "Undecided"). Check how the draft answers errors first.
- How test databases are claimed.

## Definition of done

- `uv run python-doctor . --score` prints 100, `uv run mypy .` has no errors, `uv run pytest` passes, `uv run lint-imports` passes.
- All four roles start locally against F3 and answer their health checks.
- A test proves that a session opened for the RU home cannot see EU home data, and the reverse.
- CI backend job is green after push.
