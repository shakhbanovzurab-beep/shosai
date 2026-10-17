# Staging delivery

How Shosai reaches **https://shosai.tech** (F4, [plan](../../docs/plan/packages/F4-delivery-staging.md)). This directory grows step by step: the images (steps 1–2), the staging host (step 3), the release from CI (step 4), the rollback rehearsal and runbook (step 5).

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

## The staging host

Staging runs on the development machine (F4-D1) as the Compose project `shosai-staging` in `/srv/shosai`, owned by the user `deploy` (no password, member of `docker`). Only the edge publishes ports: 80 and 443.

| Path in `/srv/shosai` | What | From |
|---|---|---|
| `compose.yaml`, `deploy/pgbouncer/` | the plane | `compose.yaml`, `pgbouncer/` here |
| `.env` | images and the edge's public settings (Compose interpolation) | `render-env.py`, then the release |
| `.env.staging` | every long-running backend role's settings | `render-env.py` |
| `secrets/` | the migrator's addresses, PgBouncer's users, Qdrant's key, Valkey and cache ACLs, the cabinet's build variables, and the secrets generated once for staging | `render-env.py` |
| `tls/shared/` | Timeweb's root, the internal CA and PgBouncer's certificate | `internal-tls.sh` |
| `tls/edge/`, `letsencrypt/`, `acme/` | the edge's certificate, certbot's state, ACME challenges | `certificate.sh` |
| `deploy/release.sh` | the deploy key's only command (owner root) | `release.sh` here |
| `releases/` | the previous images, the release history, the release lock | `release.sh` |

What runs: edge; `api`, `ws`, workers of the four queues and `scheduler` (384 MB each); PgBouncer of each home; Valkey (F4-D2: AOF, `noeviction`, ACL user, the fixed address 172.30.42.10 the gate admits); the cache; Qdrant. On 2026-10-15 the plane used about 1.5 GB. The network has IPv6 for the Russian home, whose cluster has a public IPv6 address only; dynamic addresses come from 172.30.42.128/25, so the fixed ones (edge .2, Valkey .10) stay free.

**Databases.** Each home's managed PostgreSQL (Timeweb) holds the database `shosai` with a migrator and an application role, created in Timeweb's panel, and the sweep role `shosai_sweeper` ([ADR 0053](../../docs/adr/0053-workspaces-access-rls-invitations-and-deletion.md)): it cannot log in, the application role may switch to it inside a transaction but does not inherit it ([runbook](../../docs/runbooks/staging.md#database-roles)). Migrations from workspaces step 2 on grant it privileges and policies, so it must exist before such a release. The application reaches PgBouncer over TLS with `sslmode=verify-full` against the internal CA; PgBouncer and the migrator reach the cluster with `verify-full` against Timeweb's root `CN=managed-service.timeweb.cloud` (`tls/timeweb-ca.crt`, SHA-256 `17:17:9B:AD:B9:92:FE:B0:38:42:6F:F3:1B:A6:6A:B7:FA:71:1F:09:2C:A2:27:05:BD:72:51:F3:01:1A:12:4D`, valid to 2040; both clusters present it). Migrations run on demand, so the migrator's password never lives in a long-running process.

**Visitor's country.** The edge removes `X-Country-Code` from every request: only the edge may name the country (ADR 0048), and it does not look the country up yet. The backend therefore sees no country — the interface language picks the sign-in buttons, and the first mail of an unknown visitor is written in the Russian home.

### Set up or refresh, as root

```bash
R=/root/shosai/deploy/staging
install -o deploy -g deploy -m 640 $R/compose.yaml /srv/shosai/compose.yaml
install -d -o deploy -g deploy /srv/shosai/deploy/pgbouncer
install -o deploy -g deploy $R/pgbouncer/* /srv/shosai/deploy/pgbouncer/
install -m 755 $R/certificate.sh /srv/shosai/deploy/certificate.sh
install -m 755 $R/release.sh /srv/shosai/deploy/release.sh
python3 $R/render-env.py /root/shosai/.env /srv/shosai   # generated secrets are kept
sh $R/internal-tls.sh /srv/shosai
sh /srv/shosai/deploy/certificate.sh issue /srv/shosai   # once, before the edge listens on 80
cd /srv/shosai
docker compose --profile migrate run --rm migrate upgrade
docker compose up -d
```

The certificate renews through `shosai-certificate.timer` (twice a day, `certificate.sh renew`), which copies it to `tls/edge` and reloads the edge.

## Observability

F5 ([plan](../../docs/plan/packages/F5-observability.md), step 10): the stack of [deploy/observability](../observability/README.md) runs as its own Compose project `shosai-staging-observability` in `/srv/shosai/observability`, on the plane's network, so a restart or failure of the plane does not stop the monitoring that reports it.

| Path | What | From |
|---|---|---|
| `observability/compose.yaml`, `observability/compose.staging.yaml` | the stack; the staging file takes every config, rule and dashboard from the configuration image | `deploy/observability/` |
| `observability/.env` | `COMPOSE_FILE` and `SHOSAI_OBSERVABILITY_IMAGE` | `render-env.py`, then the release |
| `secrets/alertmanager/` | the monitoring bot, chat and heartbeat address (uid 65534) | `render-env.py` from `MONITORING_TELEGRAM_*`, `HEARTBEAT_PING_URL` |
| `secrets/grafana/admin-password` | Grafana's admin password, generated once (uid 472) | `render-env.py` |
| `telemetry/probe-targets/probes.yml` | the health probe through the edge and TCP to each home's database | `render-env.py` |
| `telemetry/loki`, `telemetry/tempo` | 5 GB and 3 GB file systems (image files, systemd mount units): Loki and Tempo delete only by time, the file system caps their size | `telemetry-disks.sh` |

- The plane's services log with the Compose labels, so the collector ships their lines; the roles send traces to `collector:4318`, the edge its root spans to `collector:4317`, and business alerts go to `alertmanager:9093` (`ALERTING_ENABLED=true`).
- `grafana.shosai.tech` is a server of the edge with the same certificate (its second name, `certificate.sh expand`), proxied to `grafana:3000`, sign-in attempts limited to 10 a minute per address. The edge leaves the server out when `SHOSAI_GRAFANA_SERVER_NAME` is empty, as locally.
- Set up, as root, after the plane: `sh $R/telemetry-disks.sh /srv/shosai`, then `install -d -o deploy -g deploy /srv/shosai/observability && install -o deploy -g deploy -m 640 /root/shosai/deploy/observability/compose.yaml /root/shosai/deploy/observability/compose.staging.yaml /srv/shosai/observability/`, `render-env.py` as above, `sh /srv/shosai/deploy/certificate.sh expand /srv/shosai`. The next release brings the configuration image and starts the stack.

## Release from CI

[ADR 0050](../../docs/adr/0050-staging-release-from-ci.md). When CI passes on a push to `main` and the commit is still the head of `main`, [release.yml](../../.github/workflows/release.yml) builds the three images, pushes them to GHCR as `ghcr.io/shakhbanovzurab-beep/shosai-<backend|edge|observability>:<commit>` and calls the host over SSH. The observability image holds files only — the stack's configs, rules and dashboards (F5-D6). Releases queue; none is cancelled midway.

The application's secrets never leave the host: `render-env.py` stays their only source. The GitHub environment `staging` holds only:

| Name | Kind | What |
|---|---|---|
| `STAGING_SSH_KEY` | secret | the deploy key's private part |
| `CABINET_ENV` | secret | the cabinet's build variables, the same lines as `secrets/cabinet.env` |
| `STAGING_SSH_HOST` | variable | `shosai.tech` |
| `STAGING_SSH_KNOWN_HOSTS` | variable | `shosai.tech ssh-ed25519 …`, the host's public key |

The key's line in `/home/deploy/.ssh/authorized_keys` is `restrict,command="/srv/shosai/deploy/release.sh" ssh-ed25519 …`: the key runs nothing but [release.sh](release.sh). The script accepts only `release <actor> <backend image> <edge image> [<observability image>]` — images of this repository's GHCR namespace with a commit tag and a digest, all from one commit — and reads the job's registry token from stdin; the token pulls the images from a temporary Docker config and expires with the job.

`release.sh` follows §17: the observability stack with the commit's configuration image — the release fails unless Prometheus and Loki load exactly the rules the image holds — then migrations of both homes, then the task consumers and the scheduler, `api`, `ws` and the edge, each waiting until healthy, then `/v1/health` through the edge. `api` and `ws` are handed over with no downtime: a second container with the new image starts next to the old one, becomes healthy, the edge learns its address (it re-resolves every 10 s), and only then the old one gets SIGTERM; a request that did not reach it is retried on the new one. The edge is recreated in place when its image changes (every cabinet change): its fixed address and host ports allow one container, so connections are refused for about a second (0.7–0.9 s measured on 2026-10-16). A failed step puts the previous images back and fails the job; migrations stay (expand-only). In `/srv/shosai/releases`: `previous.env` (the images before the last release), `history.log` (one line per release: time, result, images). GHCR images other than the current and the previous release are removed from the host.

`sudo -u deploy /srv/shosai/deploy/release.sh rollback` returns to `previous.env` the same way, without migrations; the CI key cannot run it. What to do when something goes wrong: [the staging runbook](../../docs/runbooks/staging.md).

To redeploy a commit, re-run its Release workflow in GitHub. Changing an application secret: edit `/root/shosai/.env`, run `render-env.py`, then `docker compose up -d` in `/srv/shosai`. Changing the cabinet's build variables: update `CABINET_ENV` and release.

