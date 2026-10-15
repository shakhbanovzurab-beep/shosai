# Staging delivery

How Shosai reaches **https://shosai.tech** (F4, [plan](../../docs/plan/packages/F4-delivery-staging.md)). This directory grows step by step: the edge configuration now (step 2), the staging Compose file, release script and runbook in steps 3–5.

## Images

| Image | Built from | Context | Runs |
|---|---|---|---|
| backend | `backend/Dockerfile` | `backend/` | every role: `api`, `ws`, `workers --queue Q`, `scheduler`, `migrate` ([backend README](../../backend/README.md#container-image)) |
| edge | `frontend/Dockerfile` | repository root | NGINX with the cabinet's static files and the configuration in `nginx/` |

CI builds both; no server builds an image (target architecture §17).

## Edge

The edge image starts from `nginxinc/nginx-unprivileged:1.30.6-alpine`: NGINX runs as uid 101 and listens on 8080 (HTTP) and 8443 (HTTPS); the host maps 80 and 443 to them. It runs with a read-only root filesystem and a `tmpfs` at `/tmp`, where the entrypoint renders the templates.

```bash
docker buildx build -f frontend/Dockerfile --secret id=cabinet_env,src=cabinet.env -t shosai-edge .
```

`cabinet.env` holds the cabinet's build variables (`VITE_*`, [frontend/.env.example](../../frontend/.env.example)). Their values are public — the build puts them into the JavaScript — but the file comes as a build secret rather than build arguments, so the values stay out of the image's history and metadata; Vite reads it as `.env.production.local`. Without it the cabinet builds without Turnstile, GTM and the admin sign-in page. The build writes the hashes of the cabinet's inline scripts into the Content-Security-Policy.

| Variable | Meaning | Default |
|---|---|---|
| `SHOSAI_SERVER_NAME` | the domain; HTTP redirects to it | — (required) |
| `SHOSAI_TLS_CERTIFICATE`, `SHOSAI_TLS_CERTIFICATE_KEY` | paths of the certificate chain and its key, mounted read-only | — (required) |
| `SHOSAI_API_UPSTREAM` | the `api` process, `host:port` | `api:8000` |
| `SHOSAI_WS_UPSTREAM` | the `ws` gateway, `host:port` | `ws:8000` |
| `SHOSAI_CSP_STORAGE_ORIGINS` | the buckets' origins, space-separated: avatars and exports load from them | empty |
| `SHOSAI_ROBOTS_TAG` | `X-Robots-Tag` of every answer | `noindex, nofollow` |

What it serves:

- `/app/*`, `/admin/*`, `/oauth/callback`, `/unauthorized` — the cabinet: hashed assets cached for a year, `index.html` with `no-cache`;
- `/v1/ws/*` — the WS gateway (least_conn, handshake 5 s); `/v1/*` and `/email/*` — the API (connect 2 s, answer 30 s, one retry for idempotent methods, bodies up to 32 MB);
- `/` — a redirect to `/app/login` until the public site exists (F4-D5); every other path — 404;
- HTTP — only ACME challenges from `/var/www/acme` (certbot, F4-D7) and a 308 to HTTPS;
- every answer — the Content-Security-Policy, HSTS without subdomains, `nosniff`, the referrer and permissions policies and `X-Robots-Tag`;
- limits of §4.3 — 50 requests per second (burst 100) and 1 000 connections per client address, then 429;
- the client address replaces `X-Forwarded-For`, and `X-Request-ID` carries the edge's request id to the backend; the access log is JSON without query strings, which may hold tokens.

`127.0.0.1:8081/health` inside the container answers the image's health check.
