# F4 — Delivery to staging: package plan

Goal (prompt `docs/plan/prompts/F4-delivery-staging.md`): every green commit on `main` runs on **https://shosai.tech**, the
v2 test environment ([ADR 0040](../../adr/0040-shosai-tech-is-the-domain.md)), the way target architecture §17 releases
production. Planning session of 2026-10-14; no application code is written in it.

## 1. Facts this plan rests on

### 1.1 Inputs

| Fact | Source |
|---|---|
| `shosai.tech` resolves to 129.101.125.250 — the machine the development sessions run on (Timeweb, Amsterdam, AS210976): 4 vCPU, 8 GB RAM, 77 GB disk (20 GB used), no swap. Nothing listens on 80/443 | `getent hosts`, `hostname -I`, ipinfo.io, `free`, `df` on 2026-10-14 |
| From the host: GHCR, PyPI, OpenRouter, OpenAI and `challenges.cloudflare.com` are reachable | `curl` on 2026-10-14 |
| The owner's resources are in the server's `/root/shosai/.env`: admin URLs of the managed PostgreSQL of both homes (`HOME_RU_ADMIN_DATABASE_URL`, `HOME_EU_ADMIN_DATABASE_URL`), a bucket per home (`HOME_*_S3_*`), SMTP, AI provider keys, Turnstile, the social sign-in apps, identity keys. Only the names were read; values stay unread | STATUS.md F4 row; `grep -o '^[A-Z_]*='` |
| Not provided yet: the managed Valkey (EU, private network, ACL user — [ADR 0042](../../adr/0042-valkey-without-tls-inside-the-private-network.md)) | STATUS.md, `.env` |
| Several `.env` names are the draft's (`SMTP_USER`, `SMTP_TLS_MODE`, `JWT_SECRET`, `ADMIN_*`), not the settings of `.env.example` (`SMTP_ACCOUNT_USER`, `SMTP_SECURITY`, `IDENTITY_TOKEN_KEYS`…) | `.env` vs `.env.example` |
| The backend is one image with roles `api`, `ws`, `workers --queue <q>`, `scheduler`, `migrate`; every long-running role serves `/livez`, `/readyz`, `/metrics` on `OPS_PORT`; the API serves `GET /v1/health` | `backend/src/shosai/entrypoints/cli.py`, `core/web/ops.py`, `core/web/health.py` |
| Backend slices today: `identity` only. Every other cabinet screen reads paths that only the development mocks answer, and a production build has no mocks (`tooling/check-dist.ts`) | `backend/src/shosai/features/`, `frontend/src/mocks` |
| `site/` (the public Next.js site) does not exist yet | repository tree |
| CI (`.github/workflows/ci.yml`) runs on every push to `main`: repository rules, Semgrep, contracts, parity harness, backend, frontend. It builds no image and deploys nothing | ci.yml |
| Decided by the owner on 2026-10-14: GHCR as the registry; staging deploys automatically after green CI, production deploys manually with approval | this session |

### 1.2 The draft, for lessons

| Lesson | Keep as |
|---|---|
| `deploy.sh` built the frontend and installed Python on the production host | No build on any host: the image comes from GHCR (§17) |
| The backend served the SPA itself | NGINX serves the cabinet's static files (§4.2 Edge) |
| `node:20` could not read the npm 11 lock file | The frontend stage uses the Node of `frontend/.nvmrc` (26.x) |
| A host behind SNI blocking could not reach PyPI | Not a problem on this host (PyPI reachable); the build runs in GitHub Actions anyway |
| IndexNow pinged search engines from any machine | staging answers `noindex` and pings nothing |

## 2. Decisions

The owner approved the plan and F4-D1…D7 as proposed on 2026-10-14; each becomes an ADR in the step that first depends on it.

| # | Decision | Answer (approved 2026-10-14) | Trade-off |
|---|---|---|---|
| F4-D1 | **Staging runs on the development machine.** `shosai.tech` points at it | Accept for staging. A dedicated `deploy` user owns `/srv/shosai`; GitHub Actions reaches it by SSH with a key restricted to one forced command (`release.sh`). Production gets its own host when it exists | Staging secrets sit on a host that development sessions can read (§17 forbids that only for production). 8 GB RAM is shared with the IDE, the local data stack and the test databases: staging runs one process per role with capped memory |
| F4-D2 | **Valkey for staging** while the managed one is missing | Wait for the owner's managed Valkey; until then staging uses a Valkey container on the plane, on its own Compose network, AOF on, `noeviction`, ACL user — replaced by the managed one by a config change only | A container is not the managed, replicated Valkey of §4.2: a host restart loses at most a second of streams. CLAUDE.md requires your approval for this |
| F4-D3 | **Databases** | Step 3 creates the `shosai` database and the two roles (migrator, app) in each managed home from the admin URLs, and a PgBouncer container per home on the plane, as locally | The admin URLs are used once, by hand, and never by the application |
| F4-D4 | **Where staging secrets live** | GitHub environment `staging`; the deploy job writes them to `/srv/shosai/.env.staging` (mode 600, owner `deploy`) on each release. The draft-era names in `/root/shosai/.env` are mapped once into the environment's secrets, by you in the GitHub UI | Rotating a secret is a GitHub edit plus a release |
| F4-D5 | **The path `/` until `site/` exists** | NGINX redirects `/` to `/app/login`; every other non-cabinet path answers 404. Staging answers `X-Robots-Tag: noindex` everywhere | Replaced when the site package ships |
| F4-D6 | **Screens without a backend** | Ship as is: on staging, sign-in, registration, password reset, the desktop app connection and sign-out work; screens wired to identity routes that exist work too; every other section shows its error state until its slice lands | Staging shows the real state of the rewrite, not demo data |
| F4-D7 | **TLS** | certbot (pinned image) with the webroot challenge on the edge NGINX; renewal by a systemd timer that reloads NGINX | — |

## 3. Design

### 3.1 Layout

```
backend/Dockerfile          one image, four roles + migrate; python 3.14 slim, uv, non-root, no build tools at runtime
frontend/Dockerfile         node (.nvmrc) build stage → nginx stage carrying dist/ and the edge config
deploy/staging/compose.yaml edge, api, ws, workers (critical, default, bulk, meeting), scheduler, pgbouncer ×2,
                            valkey (F4-D2), redis-cache, qdrant; each with healthcheck and mem_limit
deploy/staging/nginx/       edge config: TLS, cabinet paths, /v1 → api, /v1/ws → ws (least_conn, 1013 when full),
                            /email/*, rate limits of §4.3, security headers and the CSP (Turnstile, GTM per ADR 0047)
scripts/release.sh          pull image@digest → migrate both homes → workers → scheduler → api → ws (drain) ;
                            keeps the previous digest; `release.sh rollback`
.github/workflows/release.yml  after ci.yml succeeds on main: build both images, push to GHCR, SSH deploy to staging
```

### 3.2 Release order (§17)

1. `docker compose pull` of the commit's images by digest; the previous digests are written to `/srv/shosai/releases/previous`.
2. `shosai migrate` runs once against both homes (expand-only migrations).
3. Workers and scheduler restart, then the API (`/readyz` before the old process stops), then WS drained with `server.shutdown` (up to 600 s).
4. The edge reloads only if its config changed. A failed `/readyz` or `/v1/health` stops the release and restores the previous digests.

### 3.3 Not in F4

Observability stack (F5), LiveKit and Nango (their slices), production (needs a host; §17 and ADR 0040 revisit), the public site.

## 4. Steps

| Step | Content | Skills | Done when |
|---|---|---|---|
| 1 | Backend image: multi-stage Dockerfile with the roles, non-root user, `.dockerignore`; started locally against the F3 stack | 4 Docker skills, fastapi | the image builds, each role starts and passes `/readyz` against the local stack; size and user reported. **Done 2026-10-15:** `backend/Dockerfile` (uv 0.12.21 build stage, `python:3.14.7-slim-trixie` runtime, user `1001:1001`, entrypoint `shosai`, `BIND_HOST=0.0.0.0`) and an allow-list `backend/.dockerignore`; `docker buildx build --check` finds nothing; 464 MB, about 190 MiB per idle role; `api`, `ws`, `workers` of all four queues and `scheduler` answer `/livez` and `/readyz` with a read-only root filesystem, `migrate current` reads both homes, and each role stops with exit code 0 within 2 s of SIGTERM |
| 2 | Edge image: the cabinet built into NGINX with the staging edge config; local Compose run of edge + api | 4 Docker skills, 4 Vercel skills | `/app/login`, `/v1/health` and `/v1/ws` routing work through the edge locally; config passes `nginx -t`. **Done 2026-10-15:** `frontend/Dockerfile` (context: the repository root; `node:26.10.0-trixie-slim` build, `nginxinc/nginx-unprivileged:1.30.6-alpine` runtime, uid 101, read-only root, templates rendered into `/tmp`) and `deploy/staging/nginx/`; 109 MB; `nginx -t` passes; through the edge with a self-signed certificate: `/` → 302 `/app/login`, cabinet paths → `index.html`, assets immutable, `/v1/health` and the API's JSON 404 from `api`, `/email/*` from `api`, other paths 404, HTTP → 308 and ACME; a WebSocket upgrade with its query reaches the gateway, a forged `X-Forwarded-For` is replaced; 400 parallel requests from one address → 219 × 200 and 181 × 429; the sign-in page loads with no CSP violation. The CSP for Turnstile, GTM and the Google and Yandex widgets is checked live in step 3, where their keys exist; Semgrep finds nothing |
| 3 | Staging host: `deploy` user, `/srv/shosai`, Compose for staging, databases and roles in both managed homes, PgBouncer, Valkey (F4-D2), certbot for `shosai.tech` | 4 Docker skills | `https://shosai.tech/v1/health` answers from images built and pushed by hand from CI artifacts; TLS valid. **Done 2026-10-15** (images built on the host for now; the push from CI is step 4): Timeweb creates databases and roles only in its panel, so the owner made `shosai`, a migrator and an application role in each home (the EU cluster was recreated after its grants failed to apply); `deploy` owns `/srv/shosai`; `render-env.py` maps the owner's draft-era names and generates staging's own secrets; the application reaches PgBouncer and PgBouncer and the migrator reach Timeweb with `verify-full` (internal CA; Timeweb's root pinned and checked on both clusters); the gate passes with `ENVIRONMENT=staging`; migrations at `8bf7fd2e1bd6` in both homes, the application role append-only on the audit log; Valkey on a fixed private address, IPv6 for the Russian home; Let's Encrypt for `shosai.tech` with a renewal timer (dry run passed); 13 services healthy, about 1.5 GB. Found and fixed live: redirects carried the container's port (`absolute_redirect off`), the edge passed a client's `X-Country-Code` through (now removed), the Yandex SDK needs `autofill.yandex.ru` in `connect-src`; its own Metrika calls stay blocked. The country lookup at the edge is open (owner's decision) |
| 4 | CI: `release.yml` builds both images only after a green `ci.yml` on `main`, pushes to GHCR, deploys by SSH | 4 Docker skills | a push to `main` ends with the new image running on shosai.tech |
| 5 | `scripts/release.sh` with the §17 order, drain and rollback; rollback rehearsed once; runbook in `docs/` | 4 Docker skills | rollback is one documented command and was run once |

## 5. Needed from the owner

- In GitHub: create the environment `staging` and add the secrets listed in step 3 (I prepare the list with the mapping from the draft-era names), and allow Actions to write packages to GHCR.
