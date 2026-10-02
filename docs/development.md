# Local development environment

The managed services of the target architecture — PostgreSQL and S3 in the Russian and EU data homes, managed Valkey in the EU — are not available from the hosting provider yet ([CLAUDE.md](../.claude/CLAUDE.md), "Hosting constraints now"). [`compose.dev.yaml`](../compose.dev.yaml) runs local stand-ins with the same topology, so home-aware code is developed and tested for real: two homes are two separate PostgreSQL servers, each behind its own PgBouncer, each with its own bucket.

Requirements: Docker 29.8 or later with Compose 5.5 or later. Nothing else is installed on the host.

## Start, stop, reset

| Action | Command | What it does |
|---|---|---|
| Start | `scripts/local-env.sh up` | Starts every service and returns once all health checks pass (fails after 180 s otherwise). Starting from nothing initialises the databases, roles, test databases and buckets. |
| Stop | `scripts/local-env.sh down` | Removes the containers and the network. Data stays in the volumes. |
| Reset | `scripts/local-env.sh reset` | Lists the volumes it will delete, asks for `yes`, deletes them, and starts again from nothing. `--yes` skips the question for scripted use. |
| Status | `scripts/local-env.sh status` | Shows each service and its health. |

The script is a thin wrapper over `docker compose --file compose.dev.yaml --project-name whisperer-v2-local`; any other Compose command (`logs`, `exec`, `restart`) works with the same two flags.

Reset touches only the volumes labelled with this Compose project (`whisperer-v2-local_*`). Volumes of other projects on the host, including the draft's, are never selected.

## How the homes map to the servers

| Home | PostgreSQL server | Direct port (migrations, admin) | PgBouncer | Application port | S3 bucket |
|---|---|---|---|---|---|
| Russian home | `postgres-ru` | `127.0.0.1:15432` | `pgbouncer-ru` | `127.0.0.1:16432` | `whisperer-ru` |
| EU home, also the directory | `postgres-eu` | `127.0.0.1:15433` | `pgbouncer-eu` | `127.0.0.1:16433` | `whisperer-eu` |

- Each server holds the home database `whisperer`. The database comment names its home (`\l+` in `psql`), so a misrouted connection is visible at a glance.
- The directory (target architecture §6) is a set of tables in the EU home database, not a separate server or database.
- Both buckets live in one local S3 store (SeaweedFS, `127.0.0.1:18333`). Code still configures storage per home — endpoint, region, credentials and bucket — exactly as it will for two providers.

Shared services of the compute plane:

| Service | Stands in for | Port | Notes |
|---|---|---|---|
| `valkey` | managed Valkey (EU) | `127.0.0.1:16379` | Task streams, transcript queue, locks, meeting state. AOF every second, `noeviction`, password required. |
| `redis-cache` | Redis cache container | `127.0.0.1:16380` | LRU cache only (`allkeys-lru`, 256 MB). No persistence: a restart gives a cold cache, as in production. |
| `qdrant` | Qdrant | `127.0.0.1:16333` (HTTP), `16334` (gRPC) | API key required; telemetry off. |
| `s3` | S3 of both homes | `127.0.0.1:18333` | Buckets exist from the start; uploading to a missing bucket fails, as on real S3. |

Every port listens on `127.0.0.1` only. Connection strings for all of them are in [`.env.example`](../.env.example).

## Database roles

The init script [`deploy/local/postgres/init-home.sh`](../deploy/local/postgres/init-home.sh) prepares each server the way the provider and the operator will prepare a managed one:

| Role | Rights | Connects | Used by |
|---|---|---|---|
| `postgres` | superuser | directly | administration only |
| `whisperer_migrator` | owns the databases and the `public` schema; no `SUPERUSER`, no `BYPASSRLS` | directly (`1543x`) | Alembic migrations, sweeps (target architecture §7) |
| `whisperer_app` | `CONNECT` and `TEMPORARY` only; no `SUPERUSER`, no `BYPASSRLS` | through PgBouncer (`1643x`) | the application and tests that exercise it |

- Row-level security applies to `whisperer_app` for real. A superuser or the table owner would bypass it silently.
- `whisperer_app` cannot create objects. Migrations grant it rights on tables, including the absence of `UPDATE` and `DELETE` on the audit log (§7, §15).
- The `vector` extension is created in every database by the init script, because pgvector is not a trusted extension and the migration role cannot create it.

## PgBouncer: transaction mode

Both PgBouncers run in transaction mode with protocol-level prepared statements turned off (`max_prepared_statements = 0`), the strictest reading of target architecture §19. Code that works here works behind any provider's pooler. In practice:

- The backend uses psycopg 3 with `prepare_threshold=None` ([ADR 0013](adr/0013-psycopg-driver-behind-pgbouncer.md)): every statement is sent unprepared, in one round trip, so no named statement is left on a server connection the next client reuses. Database addresses are plain libpq URLs (`postgresql://…`).
- Session state does not survive a transaction: use `SET LOCAL` inside the transaction (as for `app.org_id` and `app.user_id`, §7), never `SET`; no session advisory locks; no `LISTEN`.
- Only `whisperer_app` is known to PgBouncer. Migrations need session features and connect to the server directly.

## Migrations

One Alembic history in `backend/src/whisperer/migrations/` serves both homes ([ADR 0010](adr/0010-home-scoped-revisions-in-one-alembic-history.md)). The runner `whisperer.core.db.migrations` applies it home by home under `whisperer_migrator`, directly, with a session advisory lock and `lock_timeout = 5s`; the `whisperer migrate` command arrives with F1 step 8.

- A new revision: `uv run alembic revision -m "…"` in `backend/`. The template declares `applies_to = EVERY_HOME` and wraps `upgrade` and `downgrade` with `runs_in(applies_to)`; an EU-only revision sets `applies_to = (Home.EU,)`. Both steps receive the `MigrationScope` of the home: its `home` and the `application_role` of that home's application address.
- A new table is closed to `whisperer_app` until the revision grants it: `grant_to_application(scope, "table")`, and `revoke_from_application` in the downgrade. A company-scoped table gets row-level security with `enable_company_isolation("table")`.
- Every downgrade runs on every test run: the harness upgrades both homes of its slot to the head and downgrades them to the base at the end.

## Test databases

Every server holds prepared test databases `whisperer_test_1` … `whisperer_test_8` (`LOCAL_TEST_DATABASE_COUNT`, at most 64), owned by `whisperer_migrator`, with `vector` installed. Slot `N` has the same name on both servers, so a run that claims slot `N` has one database per home.

Backend tests use them as [ADR 0009](adr/0009-test-databases-claimed-by-advisory-lock.md) describes:

- Tests read only `TEST_*` variables (section 3 of [`.env.example`](../.env.example)): per home, the application role through PgBouncer and the migration role directly, each with the database name `whisperer_test`, plus `TEST_DATABASE_SLOTS`. The harness appends the slot number; runtime variables are never read.
- A run claims the first slot free on both servers with `pg_try_advisory_lock` over direct `whisperer_migrator` connections and holds them until it ends, so parallel runs (other agents, pytest-xdist workers) never share a slot. A crashed run's locks are released with its connections.
- Before anything is written, the harness refuses a host that is not loopback, a database name other than `whisperer_test`, a database without the `Prepared test database` comment of the init script, and a `TEST_` URL equal to a runtime URL.
- On claim it returns the slot to the state the init script prepares — it drops a crashed run's objects and the extensions `whisperer_migrator` created, and restores default privileges, rights on the `public` schema and on the database, and database settings — then records a fingerprint of each home's catalog; at the end of the run both catalogs must match it, or the run fails and names the objects.
- After the claim both homes are migrated to the head; at the end they are downgraded to the base and the version table is dropped. A test that writes application data takes the `homes` fixture, which empties every application table of both homes after it.
- Run from `backend/` with the environment up: `uv run --env-file ../.env pytest`. Tests that do not touch the databases also run without it.
- More parallel runs need more slots: raise `LOCAL_TEST_DATABASE_COUNT`, reset, and raise `TEST_DATABASE_SLOTS` (at most 15).

## Configuration

- `compose.dev.yaml` works without any `.env`. To change a port or a local password, copy [`.env.example`](../.env.example) to `.env` in the repository root and edit section 1.
- Passwords and the number of test databases are applied when a server is initialised. After changing them, run `scripts/local-env.sh reset`.
- The local passwords are for this machine only. They never appear in staging or production, and production values never appear here.
- `backend/.env` holds production values of the draft. Do not point local tools at it.

## Known messages

- Valkey and Redis log `WARNING Memory overcommit must be enabled!` when the host has `vm.overcommit_memory = 0`. It is a host kernel setting that a container cannot change. Locally it is harmless; on a production host set `vm.overcommit_memory = 1`.
- SeaweedFS logs one `connecting to peer filer … no such file or directory` line at start while its filer starts; it retries and becomes healthy.

## Lifecycle notes

- Data persists in the named volumes `postgres-ru-data`, `postgres-eu-data`, `valkey-data`, `qdrant-storage`, `qdrant-snapshots` and `s3-data` (prefixed with `whisperer-v2-local_`). The Redis cache has no volume by design.
- Every container runs with a read-only root filesystem and `no-new-privileges`, has a memory limit and rotates its logs (10 MB × 3, target architecture §14 rule 11).
- Image versions are pinned in `compose.dev.yaml` and change only through a deliberate upgrade (CLAUDE.md, "Dependencies"). Decisions behind the stand-ins are in [ADR 0001](adr/0001-local-environment.md).
