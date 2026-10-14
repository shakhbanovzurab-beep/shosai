# Local development environment

The managed services of the target architecture — PostgreSQL in the Russian and EU data homes, the one S3 bucket in Russia, managed Valkey in the EU — are not available from the hosting provider yet ([CLAUDE.md](../.claude/CLAUDE.md), "Hosting constraints now"). [`compose.dev.yaml`](../compose.dev.yaml) runs local stand-ins with the same topology, so home-aware code is developed and tested for real: two homes are two separate PostgreSQL servers, each behind its own PgBouncer, and the files of both homes live in one bucket ([ADR 0014](adr/0014-one-object-store-in-russia.md)).

Requirements: Docker 29.8 or later with Compose 5.5 or later. Nothing else is installed on the host.

## Start, stop, reset

| Action | Command | What it does |
|---|---|---|
| Start | `scripts/local-env.sh up` | Starts every service and returns once all health checks pass (fails after 180 s otherwise). Starting from nothing initialises the databases, roles, test databases and buckets. |
| Stop | `scripts/local-env.sh down` | Removes the containers and the network. Data stays in the volumes. |
| Reset | `scripts/local-env.sh reset` | Lists the volumes it will delete, asks for `yes`, deletes them, and starts again from nothing. `--yes` skips the question for scripted use. |
| Status | `scripts/local-env.sh status` | Shows each service and its health. |

The script is a thin wrapper over `docker compose --file compose.dev.yaml --project-name shosai-local`; any other Compose command (`logs`, `exec`, `restart`) works with the same two flags.

Reset touches only the volumes labelled with this Compose project (`shosai-local_*`). Volumes of other projects on the host, including the draft's, are never selected.

## How the homes map to the servers

| Home | PostgreSQL server | Direct port (migrations, admin) | PgBouncer | Application port |
|---|---|---|---|---|
| Russian home | `postgres-ru` | `127.0.0.1:15432` | `pgbouncer-ru` | `127.0.0.1:16432` |
| EU home, also the directory | `postgres-eu` | `127.0.0.1:15433` | `pgbouncer-eu` | `127.0.0.1:16433` |

- Each server holds the home database `shosai`. The database comment names its home (`\l+` in `psql`), so a misrouted connection is visible at a glance.
- The directory (target architecture §6) is a set of tables in the EU home database, not a separate server or database.
- The files of both homes and of the platform live in one bucket, `shosai`, in the local S3 store (SeaweedFS, `127.0.0.1:18333`), as production keeps one bucket in Russia (ADR 0014). The code has one storage configuration, `S3_*`; the home is not part of an object key.

Shared services of the compute plane:

| Service | Stands in for | Port | Notes |
|---|---|---|---|
| `valkey` | managed Valkey (EU) | `127.0.0.1:16379` | Task streams, transcript queue, locks, rate limits, meeting state. AOF every second, `noeviction`, password required. Staging and production reach it over TLS (`rediss://`) or, while Timeweb offers no TLS, in plain text at a private-network IP address only ([ADR 0042](adr/0042-valkey-without-tls-inside-the-private-network.md)). |
| `redis-cache` | Redis cache container | `127.0.0.1:16380` | LRU cache only (`allkeys-lru`, 256 MB). No persistence: a restart gives a cold cache, as in production. |
| `qdrant` | Qdrant | `127.0.0.1:16333` (HTTP), `16334` (gRPC) | API key required; telemetry off. |
| `s3` | the one bucket in Russia | `127.0.0.1:18333` | Bucket `shosai` exists from the start; uploading to a missing bucket fails, as on real S3. |
| `mailpit` | the SMTP server (Timeweb) | `127.0.0.1:1025` (SMTP), `8025` (web) | Accepts every mail without login or TLS and sends nothing out; read the mail at `http://127.0.0.1:8025`. Mail lives in memory: a restart empties it. |

Every port listens on `127.0.0.1` only. Connection strings for all of them are in [`.env.example`](../.env.example).

## Database roles

The init script [`deploy/local/postgres/init-home.sh`](../deploy/local/postgres/init-home.sh) prepares each server the way the provider and the operator will prepare a managed one:

| Role | Rights | Connects | Used by |
|---|---|---|---|
| `postgres` | superuser | directly | administration only |
| `shosai_migrator` | owns the databases and the `public` schema; no `SUPERUSER`, no `BYPASSRLS` | directly (`1543x`) | Alembic migrations, sweeps (target architecture §7) |
| `shosai_app` | `CONNECT` and `TEMPORARY` only; no `SUPERUSER`, no `BYPASSRLS` | through PgBouncer (`1643x`) | the application and tests that exercise it |

- Row-level security applies to `shosai_app` for real. A superuser or the table owner would bypass it silently.
- `shosai_app` cannot create objects. Migrations grant it rights on tables, including the absence of `UPDATE` and `DELETE` on the audit log (§7, §15).
- The `vector` extension is created in every database by the init script, because pgvector is not a trusted extension and the migration role cannot create it.

## PgBouncer: transaction mode

Both PgBouncers run in transaction mode with protocol-level prepared statements turned off (`max_prepared_statements = 0`), the strictest reading of target architecture §19. Code that works here works behind any provider's pooler. In practice:

- The backend uses psycopg 3 with `prepare_threshold=None` ([ADR 0013](adr/0013-psycopg-driver-behind-pgbouncer.md)): every statement is sent unprepared, in one round trip, so no named statement is left on a server connection the next client reuses. Database addresses are plain libpq URLs (`postgresql://…`).
- Session state does not survive a transaction: use `SET LOCAL` inside the transaction (as for `app.org_id` and `app.user_id`, §7), never `SET`; no session advisory locks; no `LISTEN`.
- Only `shosai_app` is known to PgBouncer. Migrations need session features and connect to the server directly.

## Migrations

One Alembic history in `backend/src/shosai/migrations/` serves both homes ([ADR 0010](adr/0010-home-scoped-revisions-in-one-alembic-history.md)). The runner `shosai.core.db.migrations` applies it home by home under `shosai_migrator`, directly, with a session advisory lock and `lock_timeout = 5s`; `uv run --env-file ../.env shosai migrate upgrade` in `backend/` runs it for both homes, RU first, and `… migrate current` logs each home's revision.

- A new revision: `uv run alembic revision -m "…"` in `backend/`. The template declares `applies_to = EVERY_HOME` and wraps `upgrade` and `downgrade` with `runs_in(applies_to)`; an EU-only revision sets `applies_to = (Home.EU,)`. Both steps receive the `MigrationScope` of the home: its `home` and the `application_role` of that home's application address.
- A new table is closed to `shosai_app` until the revision grants it: `grant_to_application(scope, "table")`, and `revoke_from_application` in the downgrade. A company-scoped table gets row-level security with `enable_company_isolation("table")`.
- Every downgrade runs on every test run: the harness upgrades both homes of its slot to the head and downgrades them to the base at the end.

## Run the backend

Every role of the one backend image runs from `backend/` with the variables of section 2 of `.env` (copy [`.env.example`](../.env.example) once: `cp -n .env.example .env`). The backend never reads `.env` itself; uv passes it.

```bash
cd backend
uv run --env-file ../.env shosai migrate upgrade    # once, and after every new revision
uv run --env-file ../.env shosai api                # public API on 127.0.0.1:8000
```

| Role | Command | Public port | Ops port |
|---|---|---|---|
| API | `shosai api` | `HTTP_PORT` (8000) | `OPS_PORT` (9100) |
| WS gateway | `shosai ws` | `HTTP_PORT` | `OPS_PORT` |
| Worker of one queue | `shosai workers --queue critical` (or `default`, `bulk`, `meeting`) | — | `OPS_PORT` |
| Scheduler | `shosai scheduler` | — | `OPS_PORT` |

- Several roles at once need different ports: `HTTP_PORT=8001 OPS_PORT=9101 uv run --env-file ../.env shosai ws`, `OPS_PORT=9102 … shosai scheduler`, and so on. A variable set on the command line wins over `.env`.
- Each role answers `http://127.0.0.1:<OPS_PORT>/livez`, `/readyz` (the status of both homes, Valkey, the cache and the bucket) and `/metrics`. The API also answers `http://127.0.0.1:8000/v1/health`.
- A role refuses to start while a home's schema is behind the code: run `shosai migrate upgrade` first. A home that is down does not stop the start: its requests get 503 until it answers again, and `/readyz` reports it `down`.
- `Ctrl+C` or `SIGTERM` stops a role cleanly: it stops taking work, finishes what is in flight, then closes. Logs are JSON lines on stdout.
- Locally every role listens on `127.0.0.1` only (`BIND_HOST`); the image binds `0.0.0.0` inside its container.

### Mail

The platform's mail goes to Mailpit with the `.env.example` defaults (`SMTP_HOST=127.0.0.1`, `SMTP_PORT=1025`, `SMTP_SECURITY=none`, no mailbox passwords). The scheduler sweeps queued mail every 2 s and a `critical` worker sends it (a `bulk` worker sends newsletters), so both must run for mail written by a feature to arrive.

```bash
uv run --env-file ../.env shosai email check --to you@example.org --locale ru
```

Mail with a secret (a code, a sign-in link) is written only with `FERNET_KEY` set: without it the feature's write fails loudly instead of losing the code. Generate a local key once with `uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.

Notifications and newsletters to a person carry a signed unsubscribe link once `EMAIL_LINK_SECRET` is set (without it they go without one). The link opens `http://127.0.0.1:8000/v1/unsubscribe?t=…` on the local API: the page asks first, the button applies it, and the person's row appears in `email_suppressions` of the home the link names. The layout's images are served at `/email/{name}`.

`shosai email check` needs no worker and no database: it sends one check mail of each kind (account, notification, newsletter) straight to the SMTP server from its mailbox, logs whether the server took each one, and exits with 1 if any was refused. The same command against the production mailboxes proves SMTP, TLS and both logins. The mails use every block of the layout, so they also show how mail looks in a client, light and dark.

## Run the frontend

The web cabinet in `frontend/` (a Vite SPA, [ADR 0021](adr/0021-public-site-on-nextjs-cabinet-on-vite.md)) needs Node.js at the version in [`frontend/.nvmrc`](../frontend/.nvmrc) and npm 11; nothing else is installed on the host.

```bash
cd frontend
npm ci                  # once, and after every change of package-lock.json
npm run dev             # http://localhost:3000/app/ with the sample API mocked in the browser (MSW)
npm run dev:api         # the same against the local backend: /v1 is proxied to BACKEND_URL (default http://localhost:8000)
```

The dev server also answers the cabinet's paths outside `/app/` (`/app`, `/admin/*`, `/oauth/callback`, `/unauthorized`) with `index.html`, as the edge does. The mocks exist only in `npm run dev` and in tests ([F2 plan](plan/packages/F2-frontend-foundation.md), F2-D1); `npm run build` fails if mock code reaches `dist/`.

| Check | Command |
|---|---|
| Types | `npm run typecheck` |
| Tests: unit, architecture rules, i18n catalogues, OpenAPI types in sync | `npm test` |
| Production bundle in `frontend/dist/` | `npm run build` |
| Code-health gate, must print `100` | `npm run doctor -- --score` |

After a change of the backend's HTTP surface, rewrite `backend/openapi.json` with `uv run --env-file <test env> pytest tests/composition/test_public_routes.py --update-openapi`, then run `npm run api:types` in `frontend/` and commit both files.

`npm run doctor` needs network: react-doctor gets the score from its vendor's service ([ADR 0020](adr/0020-react-doctor-score-from-the-vendor-service.md)). [frontend/docs/architecture.md](../frontend/docs/architecture.md) describes the layout and the boundaries.

## Test databases

Every server holds prepared test databases `shosai_test_1` … `shosai_test_8` (`LOCAL_TEST_DATABASE_COUNT`, at most 64), owned by `shosai_migrator`, with `vector` installed. Slot `N` has the same name on both servers, so a run that claims slot `N` has one database per home.

Backend tests use them as [ADR 0009](adr/0009-test-databases-claimed-by-advisory-lock.md) describes:

- Tests read only `TEST_*` variables (section 3 of [`.env.example`](../.env.example)): per home, the application role through PgBouncer and the migration role directly, each with the database name `shosai_test`, plus `TEST_DATABASE_SLOTS`. The harness appends the slot number; runtime variables are never read.
- A run claims the first slot free on both servers with `pg_try_advisory_lock` over direct `shosai_migrator` connections and holds them until it ends, so parallel runs (other agents, pytest-xdist workers) never share a slot. A crashed run's locks are released with its connections.
- Before anything is written, the harness refuses a host that is not loopback, a database name other than `shosai_test`, a database without the `Prepared test database` comment of the init script, and a `TEST_` URL equal to a runtime URL.
- On claim it returns the slot to the state the init script prepares — it drops a crashed run's objects and the extensions `shosai_migrator` created, and restores default privileges, rights on the `public` schema and on the database, and database settings — then records a fingerprint of each home's catalog; at the end of the run both catalogs must match it, or the run fails and names the objects.
- After the claim both homes are migrated to the head; at the end they are downgraded to the base and the version table is dropped. A test that writes application data takes the `homes` fixture, which empties every application table of both homes after it.
- Run from `backend/` with the environment up: `uv run --env-file ../.env pytest`. Tests that do not touch the databases also run without it.
- More parallel runs need more slots: raise `LOCAL_TEST_DATABASE_COUNT`, reset, and raise `TEST_DATABASE_SLOTS` (at most 15).

The slot also names the run's share of the shared services: database `N` of Valkey and of the Redis cache, and the prefix `tests/slot-<N>/` of the bucket.

- `TEST_VALKEY_URL` and `TEST_REDIS_CACHE_URL` carry no database index; the harness adds the slot number. Development keeps database 0.
- `TEST_S3_*` point at the development bucket: a run writes only under its prefix. The harness refuses an endpoint that is not loopback.
- A test that writes takes the `valkey`, `redis_cache` or `bucket` fixture, which empties the slot's database or prefix after it; pending multipart uploads under the prefix are aborted too. A crashed run's leftovers are removed when the next run opens the slot, and a run that ends with keys or objects left fails.

## Configuration

- `compose.dev.yaml` works without any `.env`. To change a port or a local password, copy [`.env.example`](../.env.example) to `.env` in the repository root and edit section 1.
- Passwords and the number of test databases are applied when a server is initialised. After changing them, run `scripts/local-env.sh reset`.
- The local passwords are for this machine only. They never appear in staging or production, and production values never appear here.
- `backend/.env` holds production values of the draft. Do not point local tools at it.

## Known messages

- Valkey and Redis log `WARNING Memory overcommit must be enabled!` when the host has `vm.overcommit_memory = 0`. It is a host kernel setting that a container cannot change. Locally it is harmless; on a production host set `vm.overcommit_memory = 1`.
- SeaweedFS logs one `connecting to peer filer … no such file or directory` line at start while its filer starts; it retries and becomes healthy.

## Lifecycle notes

- A volume created before ADR 0014 still holds the empty buckets `whisperer-ru` and `whisperer-eu`. Nothing reads them; `scripts/local-env.sh reset` removes them with the rest of the data.
- Mailpit keeps no volume: its mail is gone after a restart, by design.
- Data persists in the named volumes `postgres-ru-data`, `postgres-eu-data`, `valkey-data`, `qdrant-storage`, `qdrant-snapshots` and `s3-data` (prefixed with `shosai-local_`). The Redis cache has no volume by design.
- Every container runs with a read-only root filesystem and `no-new-privileges`, has a memory limit and rotates its logs (10 MB × 3, target architecture §14 rule 11).
- Image versions are pinned in `compose.dev.yaml` and change only through a deliberate upgrade (CLAUDE.md, "Dependencies"). Decisions behind the stand-ins are in [ADR 0001](adr/0001-local-environment.md).
