# F4 — Delivery to staging

Follow the common protocol in `docs/plan/prompts/README.md`. Load the four Docker skills — `docker-project-foundations`, `docker-build-strategies`, `docker-compose-patterns` and `docker-destructive-guardrails` — before starting.

## Goal

Every green commit on `main` can be deployed to **https://one.whisperer.one**, the v2 test domain, the way target architecture §17 describes production releases.

## Before starting — ask the user

Stop and ask for anything not yet provided (plan §5):

- the staging server, and SSH access for deployment;
- the DNS record for `one.whisperer.one`;
- the image registry (GHCR is proposed);
- whether staging deploys automatically after green CI and production deploys are manual with approval (proposed).

## Read first

- Target architecture §4.2 (components), §13.3 (recovery), §17 (delivery), §18.
- The draft's `Dockerfile`, `docker-compose.prod.yml`, `deploy/`, `deploy.sh` and `.github/workflows/`, for lessons only.

## Work

1. Multi-stage Dockerfile: one image with the four roles; non-root user; the built frontend served by NGINX.
2. Production Compose for the compute plane, parameterised for staging.
3. NGINX: TLS, static assets, rate limits, `/v1/ws/*` to the WS gateway with `least_conn`, 1013 when full (target architecture §4.2, §4.3).
4. TLS certificates for `one.whisperer.one` with certbot.
5. CI: build the image only from a commit whose checks passed, push it to the registry, deploy to staging.
6. `scripts/release.sh`: expand-only migrations to both homes, then workers, then API, then WS drained with `server.shutdown` (target architecture §17); keeps the previous image for rollback.
7. Staging data and secrets are separate from production and live in the CI environment's secrets, never in git and never available to development sessions.

## Definition of done

- A push to `main` ends with the new image running on https://one.whisperer.one.
- Rollback to the previous image is one documented command, rehearsed once.
- `https://one.whisperer.one/v1/health` answers from the deployed image.
