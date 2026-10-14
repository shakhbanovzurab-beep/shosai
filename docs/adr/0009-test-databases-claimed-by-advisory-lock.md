# ADR 0009 — Test databases claimed by advisory lock; tests read only `TEST_*` variables

- **Status:** accepted by the owner on 2026-10-01 (F1 planning, decision F1-D2). Amended by [ADR 0044](0044-a-bucket-per-data-home.md) (2026-10-14): `TEST_HOME_<RU|EU>_S3_*` replace `TEST_S3_*`, and tests write only under `tests/slot-<N>/` of each home's bucket.
- **Package:** F1, backend foundation; used by every backend test run.
- **Context documents:** [CLAUDE.md](../../.claude/CLAUDE.md) "Test database", "Clean up after every run", "CI"; [ADR 0001](0001-local-environment.md); [development.md](../development.md) "Test databases"; [F1 plan](../plan/packages/F1-backend-foundation.md).

## Context

- F3 prepared the databases `shosai_test_1` … `shosai_test_8` on both home servers; slot `N` has the same name on `postgres-ru` and `postgres-eu`. Several agents run tests at the same time, so each run must claim a slot no one else uses.
- Tests must exercise the application the way production runs it: under `shosai_app` through PgBouncer in transaction mode, where row-level security applies (ADR 0001); migrations run under `shosai_migrator` directly. Two homes × two roles make four database URLs, while CLAUDE.md said "tests read only `TEST_DATABASE_URL`".
- Lessons from the draft: its tests had no guard against a production database; they once wrote to the production Redis on a shared host; every test dropped and recreated the whole schema.

## Decision

1. **Tests read only variables prefixed with `TEST_`.** A runtime variable a test needs is read under its runtime name with the prefix:
   - `TEST_HOME_RU_DATABASE_URL`, `TEST_HOME_EU_DATABASE_URL` — `shosai_app` through PgBouncer;
   - `TEST_HOME_RU_MIGRATION_DATABASE_URL`, `TEST_HOME_EU_MIGRATION_DATABASE_URL` — `shosai_migrator`, directly;
   - `TEST_VALKEY_URL`, `TEST_REDIS_CACHE_URL` — without a database index, which the slot number supplies; `TEST_S3_*` (one bucket for both homes since [ADR 0014](0014-one-object-store-in-russia.md));
   - `TEST_DATABASE_SLOTS` — the number of prepared slots, at most 15.

   The database name in every database URL is `shosai_test`; the harness appends `_<slot>`. The application under test receives settings built from these values only; runtime variables such as `HOME_RU_DATABASE_URL` or `DATABASE_URL` are never read.

2. **The guard refuses to start** before anything is written, if any of these fails:
   - every host is a loopback address, the bucket's endpoint included;
   - every database name is `shosai_test`, and the claimed database's comment starts with `Prepared test database` (set by the F3 init script and nowhere else);
   - the Valkey and Redis database index replaced by the slot is not 0, which development uses;
   - no database, Valkey or cache `TEST_` URL equals a runtime URL present in the environment. The bucket's endpoint may equal the development one: locally both use the one bucket of the local store, and a run writes only under `tests/slot-<N>/` and empties it after every test. (Amended by the owner on 2026-10-02, F1-D11; the first version applied the rule to every `TEST_` URL, which the one local bucket of ADR 0014 cannot satisfy.)

3. **Claiming.** For slot 1 … N, the harness opens a direct `shosai_migrator` connection to `shosai_test_<slot>` in the RU home and calls `pg_try_advisory_lock` on a fixed key, then does the same in the EU home. The first slot locked in both homes is the run's; the connections stay open until the run ends. A crashed run's connections close, so its locks are released without any manual step. No free slot fails the run with a message naming N. Each pytest-xdist worker, if used, claims its own slot.

4. **State.** A catalog fingerprint covers every object in the database that does not belong to an extension: relations, types, functions, schemas, policies, triggers, grants and default privileges, plus the installed extensions and the database's rights and settings.
   - On claim, the slot is returned to the state the F3 init script prepares, and only then is the fingerprint taken as the reference. A crashed run's objects are dropped: non-extension objects in `public`, other schemas, extensions owned by `shosai_migrator`. What does not go away with objects is restored: the migrator's default privileges, the owner and rights of the `public` schema, the rights on the database and its settings. On a clean slot this changes nothing. Without it, a right a crashed run had changed would enter the next run's reference, and that run's downgrade would fail it. (Amended by the owner on 2026-10-02; the first version dropped only objects in `public`.)
   - The run applies `alembic upgrade head` to both homes.
   - After each test, every application table in both homes is truncated through the migrator connection; the slot's Valkey and Redis databases are flushed; objects under `tests/slot-<N>/` in the bucket are deleted.
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
