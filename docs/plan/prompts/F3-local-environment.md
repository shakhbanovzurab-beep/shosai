# F3 — Local environment

Follow the common protocol in `docs/plan/prompts/README.md`. Load the skills `docker-project-foundations`, `docker-compose-patterns` and `docker-destructive-guardrails` before starting.

## Goal

A local environment that stands in for the hosting that does not exist yet (CLAUDE.md "Hosting constraints now"), so the home-aware design is developed and tested for real.

## Read first

- Target architecture §4 (topology), §6 (residency), §16 (observability), §18 (versions).
- The draft's `docker-compose*.yml` and `backend/docker-compose.yml`, for lessons only.

## Work

1. `compose.dev.yaml` in the repository root with pinned image tags:
   - PostgreSQL 18 with pgvector as **two separate servers**, `postgres-ru` and `postgres-eu`, standing in for the two homes; the EU one also holds the directory;
   - Valkey 9.1 for task streams, locks and the transcript queue (with AOF, like the managed service);
   - Redis as the LRU cache;
   - Qdrant;
   - an S3-compatible store with one bucket per home;
   - health checks and named volumes for all of them.
2. Prepared test databases on the PostgreSQL servers for parallel test runs (CLAUDE.md "Test database"), created by an init script.
3. One command to start, one to stop, one to reset data, documented in `docs/development.md`. Reset only touches this project's local volumes.
4. `.env.example` entries for every local connection string. Local values only; no production values anywhere.

## Definition of done

- The environment starts from nothing with one command, and all health checks pass.
- `docs/development.md` explains start, stop, reset and how the two homes map to the two servers.
- Nothing binds to public interfaces; ports listen on `127.0.0.1` only.
