# F4 — Delivery to staging

Follow the common protocol in `docs/plan/prompts/README.md`. Load the four Docker skills — `docker-project-foundations`, `docker-build-strategies`, `docker-compose-patterns` and `docker-destructive-guardrails` — before starting; load `fastapi` before touching `backend/` and the four Vercel skills before touching `frontend/`.

**This package is multi-session.** Work in the session mode described in `docs/plan/prompts/README.md`; the package plan is `docs/plan/packages/F4-delivery-staging.md`. The planning session asks the user for everything in "Before starting". Steps 1–5 need only F1; step 6 needs F2. A split that fits the work below — adjust it in the plan if the design needs another order:

1. Backend image: multi-stage Dockerfile with the four roles, non-root user, `.dockerignore`; built and started locally against F3 (item 1, backend part).
2. Staging server: production Compose for the compute plane, parameterised for staging; NGINX with TLS from certbot, rate limits, `/v1/ws/*` with `least_conn` and 1013 when full (items 2, 3, 4). Needs the server and the DNS record.
3. Staging data stores and secrets: staging's own databases for both homes, object store and Valkey — the managed services the owner provides, or what the user decides while they are missing (CLAUDE.md "Hosting constraints now"); secrets only in the CI environment (item 7).
4. CI: build the image only from a green commit, push it to the registry, deploy to staging (item 5).
5. `scripts/release.sh` with the migration and drain order of §17, keeping the previous image; the rollback command rehearsed once (item 6, definition of done).
6. Frontend: the built frontend in the image, served by NGINX (item 1, frontend part).

## Goal

Every green commit on `main` can be deployed to **https://shosai.tech**, the v2 test domain, the way target architecture §17 describes production releases.

## Before starting — ask the user

Stop and ask for anything not yet provided (plan §5):

- the staging server, and SSH access for deployment;
- the DNS record for `shosai.tech`;
- the image registry (GHCR is proposed);
- whether staging deploys automatically after green CI and production deploys are manual with approval (proposed).

## Read first

- Target architecture §4.2 (components), §13.3 (recovery), §17 (delivery), §18.
- The draft's `Dockerfile`, `docker-compose.prod.yml`, `deploy/`, `deploy.sh` and `.github/workflows/`, for lessons only.

## Work

1. Multi-stage Dockerfile: one image with the four roles; non-root user; the built frontend served by NGINX.
2. Production Compose for the compute plane, parameterised for staging.
3. NGINX: TLS, static assets, rate limits, `/v1/ws/*` to the WS gateway with `least_conn`, 1013 when full (target architecture §4.2, §4.3).
4. TLS certificates for `shosai.tech` with certbot.
5. CI: build the image only from a commit whose checks passed, push it to the registry, deploy to staging.
6. `scripts/release.sh`: expand-only migrations to both homes, then workers, then API, then WS drained with `server.shutdown` (target architecture §17); keeps the previous image for rollback.
7. Staging data and secrets are separate from production and live in the CI environment's secrets, never in git and never available to development sessions.

## Definition of done

- A push to `main` ends with the new image running on https://shosai.tech.
- Rollback to the previous image is one documented command, rehearsed once.
- `https://shosai.tech/v1/health` answers from the deployed image.
