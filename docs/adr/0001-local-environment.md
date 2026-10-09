# ADR 0001 — Local stand-ins for the managed data services

- **Status:** proposed. The owner confirmed SeaweedFS and a PgBouncer per home on 2026-10-01; `max_prepared_statements = 0` and the two roles await confirmation.
- **Package:** F3, local environment
- **Context documents:** [ARCHITECTURE.md](../design/ARCHITECTURE.md) §4.1, §6, §7, §14 rule 2, §19; [CLAUDE.md](../../.claude/CLAUDE.md) "Hosting constraints now"

## Context

The target architecture places data in two homes — a managed PostgreSQL cluster behind PgBouncer plus an S3 bucket in Russia and in the EU — and uses managed Valkey in the EU. None of these exist yet. Code must still be written and tested home-aware, against local containers ([development.md](../development.md)). Three choices are not settled by the architecture, the plan or the draft (the draft has no local S3 and no local pooler).

## Decisions

1. **S3 stand-in: SeaweedFS 4.48** (`chrislusf/seaweedfs`, `weed mini`), one store with one bucket per home (one bucket for both homes since [ADR 0014](0014-one-object-store-in-russia.md)).
   MinIO, the usual choice, stopped publishing community images in late 2025, and its repository was archived in early 2026. Before adoption, SeaweedFS was checked here for every operation the design relies on:
   - signed put and get;
   - presigned GET, with a tampered URL rejected;
   - multipart upload;
   - lifecycle rules with `AbortIncompleteMultipartUpload` and expiration;
   - rejection of a wrong secret and of anonymous access;
   - no implicit bucket creation.

   It runs as a non-root user on a read-only root filesystem. RustFS 1.0.0 was the alternative; it was released two weeks before this decision.

2. **One PgBouncer per home, transaction mode, `max_prepared_statements = 0`** (`edoburu/pgbouncer:v1.26.0-p0`, PgBouncer 1.26.0). The application connects only through it; migrations connect to the server directly.
   - §19 states that transaction mode forbids session-bound features, including prepared statements, and that each use must be checked. A local pooler makes that check happen on every developer run instead of first on staging.
   - Prepared statements are off although PgBouncer 1.24+ can track them, because the managed provider's pooler and its settings are unknown. Code that passes with them off passes on any pooler.
   - No official PgBouncer image exists. `edoburu/pgbouncer` is the widely used community image. It is configured here by committed files and a start script, not by its environment-driven entrypoint.

3. **Two database roles besides the superuser**, created by the init script on both servers:
   - `shosai_migrator` owns the databases and schema;
   - `shosai_app` has no `SUPERUSER` and no `BYPASSRLS`.

   §7 relies on row-level security, which a superuser or the table owner bypasses silently. Tests and development must run the application under the role production will use. Migrations grant table rights to the application role.

## Consequences

- Backend code must turn asyncpg's statement cache off. The default cache fails behind the local PgBouncer with `prepared statement "__asyncpg_stmt_N__" does not exist`; this was observed during verification. (Superseded by [ADR 0013](0013-psycopg-driver-behind-pgbouncer.md) on 2026-10-02: the backend uses psycopg 3 without server-side prepared statements.)
- Session `SET`, session advisory locks and `LISTEN` are unavailable to the application; `SET LOCAL` per transaction is the pattern (§7).
- Two third-party images that are not Docker official images (SeaweedFS, edoburu/pgbouncer) are pinned by tag in a development-only file. They never run in staging or production.
- Both buckets share one local store and one key pair; per-home storage configuration in code is still separate. (Superseded by [ADR 0014](0014-one-object-store-in-russia.md) on 2026-10-02: the local store keeps one bucket, `shosai`, as production keeps one bucket in Russia; the code has one storage configuration, `S3_*`.)

## Revisit when

- The managed providers are chosen: match PgBouncer settings (in particular `max_prepared_statements`) and S3 features to theirs.
- SeaweedFS lacks an S3 feature that a slice needs, or the providers' S3 behaviour differs in a way that matters to tests.
- An official PgBouncer image appears, or `edoburu/pgbouncer` stops being maintained.
