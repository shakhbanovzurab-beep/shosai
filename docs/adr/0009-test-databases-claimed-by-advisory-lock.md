# ADR 0009 — Test databases claimed by advisory lock; tests read only `TEST_*` variables

- **Status:** accepted by the owner on 2026-10-01 (F1 planning, decision F1-D2).
- **Package:** F1, backend foundation; used by every backend test run.
- **Context documents:** [CLAUDE.md](../../.claude/CLAUDE.md) "Test database", "Clean up after every run", "CI"; [ADR 0001](0001-local-environment.md); [development.md](../development.md) "Test databases"; [F1 plan](../plan/packages/F1-backend-foundation.md).

## Context

- F3 prepared the databases `whisperer_test_1` … `whisperer_test_8` on both home servers; slot `N` has the same name on `postgres-ru` and `postgres-eu`. Several agents run tests at the same time, so each run must claim a slot no one else uses.
- Tests must exercise the application the way production runs it: under `whisperer_app` through PgBouncer in transaction mode, where row-level security applies (ADR 0001); migrations run under `whisperer_migrator` directly. Two homes × two roles make four database URLs, while CLAUDE.md said "tests read only `TEST_DATABASE_URL`".
- Lessons from the draft: its tests had no guard against a production database; they once wrote to the production Redis on a shared host; every test dropped and recreated the whole schema.

## Decision

1. **Tests read only variables prefixed with `TEST_`.** A runtime variable a test needs is read under its runtime name with the prefix:
   - `TEST_HOME_RU_DATABASE_URL`, `TEST_HOME_EU_DATABASE_URL` — `whisperer_app` through PgBouncer;
   - `TEST_HOME_RU_MIGRATION_DATABASE_URL`, `TEST_HOME_EU_MIGRATION_DATABASE_URL` — `whisperer_migrator`, directly;
   - `TEST_VALKEY_URL`, `TEST_REDIS_CACHE_URL`, `TEST_HOME_RU_S3_*`, `TEST_HOME_EU_S3_*`;
   - `TEST_DATABASE_SLOTS` — the number of prepared slots, at most 15.

   The database name in every database URL is `whisperer_test`; the harness appends `_<slot>`. The application under test receives settings built from these values only; runtime variables such as `HOME_RU_DATABASE_URL` or `DATABASE_URL` are never read.

2. **The guard refuses to start** before anything is written, if any of these fails:
   - every host is a loopback address;
   - every database name is `whisperer_test`, and the claimed database's comment starts with `Prepared test database` (set by the F3 init script and nowhere else);
   - the Valkey and Redis database index replaced by the slot is not 0, which development uses;
   - no `TEST_` URL equals a runtime URL present in the environment.

3. **Claiming.** For slot 1 … N, the harness opens a direct `whisperer_migrator` connection to `whisperer_test_<slot>` in the RU home and calls `pg_try_advisory_lock` on a fixed key, then does the same in the EU home. The first slot locked in both homes is the run's; the connections stay open until the run ends. A crashed run's connections close, so its locks are released without any manual step. No free slot fails the run with a message naming N. Each pytest-xdist worker, if used, claims its own slot.

4. **State.** A catalog fingerprint covers every object in the database that does not belong to an extension: relations, types, functions, schemas, policies, triggers, grants and default privileges.
   - On claim, leftovers of a crashed run (non-extension objects in `public`) are dropped and the fingerprint is taken as the reference.
   - The run applies `alembic upgrade head` to both homes.
   - After each test, every application table in both homes is truncated through the migrator connection; the slot's Valkey and Redis databases are flushed; objects under `tests/slot-<N>/` in both buckets are deleted.
   - At the end, `alembic downgrade base` runs in both homes and the fingerprint must equal the reference. A difference fails the run and names the objects.

5. **CI uses the same mechanism** against the same `compose.dev.yaml` services, normally on slot 1.

## Consequences

- CLAUDE.md "Test database" and "CI" now say "only `TEST_*` variables"; `.env.example` and `docs/development.md` document the variables.
- Every migration must have a working downgrade, because every run executes it.
- Valkey has 16 logical databases and development uses 0, so at most 15 slots; the default 8 fits.
- Per-test truncation costs a few milliseconds per test; it is measured when the suite grows.

## Revisit when

- Test databases move to a shared remote server: advisory locks still work, the loopback rule must be widened deliberately.
- Truncation dominates the run time: switch the hot tests to transaction-scoped fixtures.
