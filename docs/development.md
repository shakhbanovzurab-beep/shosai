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

- asyncpg's statement cache must be off (`statement_cache_size=0`, and in SQLAlchemy `prepared_statement_cache_size=0`). With the default cache, queries fail with `prepared statement "__asyncpg_stmt_N__" does not exist`.
- Session state does not survive a transaction: use `SET LOCAL` inside the transaction (as for `app.org_id` and `app.user_id`, §7), never `SET`; no session advisory locks; no `LISTEN`.
- Only `whisperer_app` is known to PgBouncer. Migrations need session features and connect to the server directly.

## Test databases

Every server holds prepared test databases `whisperer_test_1` … `whisperer_test_8` (`LOCAL_TEST_DATABASE_COUNT`, at most 64), owned by `whisperer_migrator`, with `vector` installed. Slot `N` has the same name on both servers, so a run that claims slot `N` has one database per home.

How a run claims a free slot, and how tests address the second home, is defined by package F1 in its ADR. Whatever the mechanism, the rules in CLAUDE.md "Test database" apply: tests read only `TEST_DATABASE_URL`, refuse anything that is not a test database, and leave data and schema exactly as they found them.

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
