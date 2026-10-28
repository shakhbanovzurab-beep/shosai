# Runbook — staging on shosai.tech

What to do when staging needs a hand. How staging is built: [deploy/staging/README.md](../../deploy/staging/README.md); why: [ADR 0050](../adr/0050-staging-release-from-ci.md). Commands run as root on the staging host unless noted; the plane is the Compose project in `/srv/shosai`.

## What is running

```bash
cd /srv/shosai
grep IMAGE .env                      # the images of the running release
tail -n 5 releases/history.log       # time, result (released, rolled-back, failed), backend, edge, observability
docker compose ps                    # every service and its health
curl -fsS https://shosai.tech/v1/health
```

`releases/previous.env` names the images the next rollback returns to.

## A release failed

The Release workflow in GitHub fails, and `history.log` gets a `failed` line. `release.sh` has already put the previous images back; the job log says either "прежние образы снова работают" or "прежние образы не поднялись: нужен человек".

1. Read the failing step in the job log: migrations, a role that did not become healthy, or `/v1/health` through the edge.
2. For a role that did not start: `docker compose logs --tail 200 <service>`; the critical line names the start step that failed (backend README, "Start").
3. If the previous images did not come back either, run a rollback (below), then `docker compose up -d` for anything still down.
4. Fix the cause in a new commit; its green CI releases it. Migrations of the failed release stay applied: they are expand-only, and the previous code works with them.

## Roll back

Back to the images before the last release, without migrations, `api` and `ws` replaced with no downtime:

```bash
sudo -u deploy /srv/shosai/deploy/release.sh rollback
```

It ends with "готово: rolled-back" and a `rolled-back` line in `history.log`. Running it again returns to the images that were rolled back. A rollback is not possible over SSH: the CI key may only release.

The next green commit on `main` releases over a rollback. To keep staging on the rolled-back images, do not push to `main` until the fix is ready.

## Release a commit again

In GitHub, open the commit's Release run and choose "Re-run all jobs". A commit is released only when it is newer than the one staging runs (the latest successful deploy's): a re-run of an older or the same commit skips itself after its first job, which says so in its log.

## Change a setting or a secret

Application settings and secrets live only on the host (ADR 0050):

```bash
$EDITOR /root/shosai/.env
python3 /root/shosai/deploy/staging/render-env.py /root/shosai/.env /srv/shosai
cd /srv/shosai && sudo -u deploy docker compose up -d
```

Compose recreates the services whose environment changed. The cabinet's build variables (`VITE_*`) are compiled into the edge image: change `CABINET_ENV` in the GitHub environment `staging`, then release again.

## Rename a setting

A release whose code reads a setting under a new name must not leave the previous images without the old one: they start again after a host reboot and on `release.sh rollback`. The rename therefore spans two commits (first used for `MEETINGS_*` → `NOTES_*`, ADR 0057):

1. **The rename commit.** The code and `.env.example` use the new name; `render-env.py` writes both names with the same value, through a map from the new name to the old one. Before pushing, render the environment without recreating any service — the running containers keep the environment they were created with, and the release recreates them with the new file:

   ```bash
   python3 /root/shosai/deploy/staging/render-env.py /root/shosai/.env /srv/shosai
   ```

   Do not run `docker compose up -d` here: the current images would be recreated against a file they were not released with. Push, then wait for CI and the release.
2. **The clean-up commit, once that release is healthy.** Remove the old names from `render-env.py` and push. Render the environment again only after this second release: until then the rollback target is still the images from before the rename, which need the old names. From then on `release.sh rollback` returns to the release that reads the new names.

If the owner set the old name in `/root/shosai/.env`, rename it there before the first render (check the key names only: `grep -o '^OLD_PREFIX_[A-Z_]*' /root/shosai/.env`).

## Replace the deploy key

```bash
umask 077
ssh-keygen -q -t ed25519 -N "" -C "github-actions-staging-deploy" -f /root/staging-deploy-key
printf 'restrict,command="/srv/shosai/deploy/release.sh" %s\n' "$(cat /root/staging-deploy-key.pub)" \
  > /home/deploy/.ssh/authorized_keys
chown deploy:deploy /home/deploy/.ssh/authorized_keys
```

Put the private key into the secret `STAGING_SSH_KEY`, release once, then `rm /root/staging-deploy-key`.

## Update release.sh

`release.sh` runs from `/srv/shosai/deploy/`, not from the repository. After a change is committed:

```bash
install -o root -g root -m 755 /root/shosai/deploy/staging/release.sh /srv/shosai/deploy/release.sh
```

Do it while no release runs (`flock -n /srv/shosai/releases/.lock true` succeeds).

## Bucket rules

Each home's bucket needs ADR 0055's rules before files can be uploaded from the cabinet: run `shosai files bucket-rules` once per new bucket with keys that may configure it (the release's environment, `docker compose run --rm api shosai files bucket-rules`). The CORS rule admits the cabinet's origin from `PUBLIC_BASE_URL` (`https://shosai.tech`); `CORS_ALLOWED_ORIGINS` stays empty on staging, since the cabinet and the API share one origin. A failed home is named in the log; a repeat changes nothing.

## Downloads

Files download through the edge (ADR 0055 point 8, FL-D9): the API answers `https://shosai.tech/dl/{home}/…`, and the edge streams the presigned object from that home's bucket (`SHOSAI_DOWNLOAD_RU_ORIGIN`, `SHOSAI_DOWNLOAD_EU_ORIGIN` in `/srv/shosai/.env`) with `X-Content-Type-Options: nosniff` and `Content-Security-Policy: sandbox`. `render-env.py` writes both origins from the homes' `HOME_*_S3_ENDPOINT_URL` (HTTPS only) and `FILES_DOWNLOAD_BASE_URL` for the backend. Without them a release stops before any service changes: run «Change a setting or a secret» first. A download answering 403 from the bucket means the signature did not survive the path; the edge forwards the raw request line, so check that nothing between the browser and the edge rewrites it.

## Leo's model

Outside development the backend refuses to start without `AGENT_STANDARD_MODEL` and `AGENT_UTILITY_MODEL` (ADR 0068 AG-D4): the OpenRouter models Leo answers with, and writes threads' titles and summaries with, until studio publishes its routes. `render-env.py` writes `google/gemini-3.8-flash` for both, with the fallback `anthropic/claude-haiku-5.5` for answers, or the owner's `AGENT_*_MODEL` and `AGENT_*_FALLBACK_MODEL` from `/root/shosai/.env` when set. A release that stops at the `settings` step naming it needs «Change a setting or a secret» first. A process with `LANGSMITH_TRACING` or `LANGCHAIN_TRACING_V2` on refuses to start: a conversation never goes to LangSmith.

## Meetings' notes model

Outside development the backend refuses to start without `NOTES_MODEL` (notes plan step 6): the OpenRouter model that writes the findings and Leo's write-up until studio assigns the `notes` role. `render-env.py` writes `google/gemini-3.8-flash`, or the owner's `NOTES_MODEL` and `NOTES_FALLBACK_MODEL` from `/root/shosai/.env` when set. A release that stops at the `settings` step naming it needs «Change a setting or a secret» first.

The same holds for `NOTES_TRANSCRIBE_MODEL` (notes plan steps 9a and 29): the OpenRouter model that transcribes imported and desktop recordings with timed segments and their speakers. `render-env.py` writes `elevenlabs/scribe-v2` ([ADR 0073](../adr/0073-recordings-transcribed-with-speakers-by-scribe.md); priced per second of audio by revision `c4d1f7a9e2b6`, OpenRouter reports each call's cost), or the owner's `NOTES_TRANSCRIBE_MODEL` and `NOTES_TRANSCRIBE_FALLBACK_MODEL` when set. `NOTES_MEDIA_SECONDS` (300) and `NOTES_MEDIA_MEMORY_MB` (1024) bound each `ffprobe` and `ffmpeg` call; the defaults need no entry. pyannote is no longer used: `PYANNOTE_API_KEY` and `NOTES_DIARIZE_MODEL` are not written, and the owner's file may drop them.

**Recordings without speakers.** Speakers come from the transcription model itself. When the run's lines carry none, the workers-meeting log shows `Запись расшифрована без говорящих` with the run's id: the fallback model (`NOTES_TRANSCRIBE_FALLBACK_MODEL`) answered, because the primary failed — look for the primary's `provider_error` or `rate_limited` before it. The run still ends `succeeded` with the transcript and Leo's notes; a later recording of the same meeting replaces its lines. Runs that ended `partially_completed` before ADR 0073 lost their pyannote diarization and keep that state.

## Database roles

Each managed home has three roles: the migrator and the application role (Timeweb's panel), and the sweep role `shosai_sweeper` ([ADR 0053](../adr/0053-workspaces-access-rls-invitations-and-deletion.md) point 2). The sweep role cannot log in; workers and the scheduler switch to it inside a transaction (`SET LOCAL ROLE`), and row-level security lets it read every tenant's rows. The application role must not inherit it, or every request would see every tenant. PostgreSQL 16 or later is required for `WITH INHERIT FALSE`.

Create it once per home, as a role with `CREATEROLE` — on Timeweb the migrator has it — before releasing a commit whose migrations name it. Done on both staging homes on 2026-10-17 (PostgreSQL 18.6):

```sql
CREATE ROLE shosai_sweeper NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
GRANT shosai_sweeper TO <application role> WITH INHERIT FALSE, SET TRUE;
```

Check: `SELECT r.rolname, m.inherit_option, m.set_option FROM pg_auth_members m JOIN pg_roles r ON r.oid = m.roleid JOIN pg_roles u ON u.oid = m.member WHERE u.rolname = '<application role>';` returns `shosai_sweeper | f | t`.

## The `vector` extension

Memory's tables (revision `e8bc01bd5bb4`, ADR 0071 MM-D6) need pgvector 0.5 or later in the database `shosai` of each home. The extension is not trusted, so the migrator cannot create it: `CREATE EXTENSION IF NOT EXISTS vector` in the migration fails with `permission denied to create extension "vector"`, and the release rolls back to the previous images. Enable it once per home before releasing such a commit — in Timeweb's panel (the database's extensions), through Timeweb's support, or as the cluster's administrator:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Check, as the migrator: `SELECT extversion FROM pg_extension WHERE extname = 'vector';` returns a version, and `SELECT '[1,2]'::halfvec(2);` succeeds. Then release the commit again ([Release a commit again](#release-a-commit-again)). Done on both staging homes on 2026-10-27: the RU home already had it, the owner enabled it in the EU home after releases from `f25187da` (14:40 UTC) on had rolled back on this error, and the release of `2f963992` (17:05 UTC) migrated both.

## TLS certificate

One certificate covers `shosai.tech`, `grafana.shosai.tech`, `rtc.shosai.tech` and `turn.shosai.tech`; the edge terminates TLS for all of them, LiveKit holds none. A new name is added with `sh /srv/shosai/deploy/certificate.sh expand /srv/shosai` once its DNS record points here. `shosai-certificate.timer` renews it twice a day. Check: `systemctl list-timers shosai-certificate.timer` and `journalctl -u shosai-certificate.service`. Renew by hand: `sh /srv/shosai/deploy/certificate.sh renew /srv/shosai`.

## Calls (LiveKit)

Calls run on this host (meetings A15, ADR 0072 MR-D14): `livekit`, `livekit-redis` and `egress` in the plane's Compose project. The edge takes signalling on `rtc.shosai.tech` and TURN/TLS on `turn.shosai.tech`, both on 443 by SNI; the media ports are LiveKit's own. Staging's ceilings: 4 participants in a call, one video recording at a time, 30 minutes long (`livekit_files.py`). Limits: LiveKit 512 MB and 1 CPU (`GOMEMLIMIT` 460 MiB), its Redis 64 MB, egress 1 GB and 1 CPU — memory equal to the swap limit, so nothing of LiveKit swaps.

```bash
cd /srv/shosai
sudo -u deploy docker compose ps livekit livekit-redis egress
sudo -u deploy docker compose logs --tail 100 livekit
curl -fsS https://rtc.shosai.tech/                 # LiveKit answers OK through the edge
```

- **LiveKit is not part of a release.** `release.sh` swaps the roles and the edge, never LiveKit: recreating it ends every call in progress. Its image, limits or configuration change by editing `deploy/staging/compose.yaml` or `livekit_files.py`, installing and rendering them («Change a setting or a secret»), then `sudo -u deploy docker compose up -d --force-recreate livekit egress` at a time with no calls (the admin's LiveKit screen shows the rooms; `livekit_room_total` in Prometheus is 0). A change of `secrets/livekit.yaml` alone is invisible to Compose, so it needs the recreate too.
- **Egress follows LiveKit.** Egress lives in LiveKit's network namespace, joined when egress starts. After LiveKit restarts, restart egress as well, after it: `sudo -u deploy docker compose restart livekit && sudo -u deploy docker compose restart egress`. Restarting both in one command may start egress first, in the old namespace, where it reaches nothing (found 2026-10-28); check with `docker exec shosai-staging-egress-1 wget -qO- http://127.0.0.1:7880` — it answers `OK`.
- **The keys** are `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET` in `/root/shosai/.env`; `render-env.py` writes them into LiveKit's, egress's and the backend's files together. After a change recreate `livekit`, `egress` and the roles in one go, or webhooks fail verification (`LiveKitWebhooksRejected`).
- **Release order.** The edge and the roles start without LiveKit: the edge resolves `livekit` on each connection, and the backend answers call routes with 503 `video_unavailable` until LiveKit answers. LiveKit's webhooks reach `api` on the plane's network (`http://api:8000/v1/livekit/webhook`), so a release's handover of `api` loses none.

### Exposure (MR-D14)

The host has no firewall, neither its own nor in the provider's panel: whatever listens on a public address is open to everyone. So exposure is decided by how each port is bound, and only these may listen outside:

| Port | What |
|---|---|
| TCP 443 | the edge: the cabinet, Grafana, LiveKit's signalling (`rtc`) and TURN/TLS (`turn`), split by SNI |
| TCP 80 | the edge: ACME challenges for certbot and the redirect to HTTPS |
| TCP 7881 | LiveKit: ICE over TCP |
| UDP 7882 | LiveKit: ICE over UDP, every call's media |
| UDP 3478 | LiveKit: TURN over UDP |
| UDP 30000–30099 | LiveKit: TURN relay ports |
| TCP 22 | `sshd`: the owner's and the release key's access |
| TCP 10050 | `zabbix_agentd`, the provider's monitoring agent (found 2026-10-27, not Shosai's) |
| UDP 68, UDP 546 | `systemd-networkd`'s DHCP clients (IPv4 and IPv6): the host's own address leases, not services |

LiveKit's media ports are published on IPv4 only: LiveKit advertises the host's IPv4 (`node_ip`), and `shosai.tech` has no AAAA record. LiveKit's API and metrics (7880, 6789), egress (8080, 9090), every Redis, Valkey, Qdrant, PgBouncer and the observability stack listen only on the plane's network or on loopback.

Check after any change to a Compose file, and after each host reboot:

```bash
# Every socket listening on a non-loopback, non-private address.
ss -Htlnup | awk '{print $1, $5, $7}' | grep -vE ' (127\.|\[::1\]|172\.|\[fd)' | sort -u
# From another machine: TCP and the media's UDP ports.
nmap -Pn -p- --min-rate 2000 shosai.tech
sudo nmap -Pn -sU -p 3478,7882,30000-30099 shosai.tech
```

The `ss` list must hold exactly the ports of the table (each LiveKit port appears as `docker-proxy`; on 2026-10-28 the 103 LiveKit ports added 103 `docker-proxy` processes, about 530 MB). An external TCP scan must find only 22, 80, 443, 7881 and 10050; UDP answers depend on the protocol, so open ports there show as `open|filtered`.

## Observability

The observability stack is its own Compose project in `/srv/shosai/observability` (`shosai-staging-observability`), so a restart of the plane does not stop the monitoring that reports it. Its configs, rules and dashboards come from the release's configuration image (`SHOSAI_OBSERVABILITY_IMAGE` in its `.env`); its secrets are files under `/srv/shosai/secrets/{alertmanager,grafana}` rendered by `render-env.py`.

```bash
cd /srv/shosai/observability
sudo -u deploy docker compose ps                 # every service and its health
sudo cat /srv/shosai/secrets/grafana/admin-password   # Grafana's admin password, https://grafana.shosai.tech
df -h /srv/shosai/telemetry/loki /srv/shosai/telemetry/tempo   # the size caps of Loki and Tempo
```

- **A release failed at «стек наблюдаемости».** Either a service did not become healthy (`docker compose logs --tail 100 <service>`) or the rules Prometheus or Loki loaded differ from the image's (the job log names the counts). The release put the previous configuration back.
- **DEBUG lines of one person:** `sudo -u deploy docker compose -f /srv/shosai/compose.yaml exec api shosai observability debug --user <id> --minutes 15 --reason "…"` ([docs/observability.md](../observability.md)).
- **Cronitor alerts that the heartbeat stopped** (`shosai-alerting`): Prometheus, Alertmanager or the host is down — start with `docker compose ps` here.
- **UptimeRobot alerts** (`shosai.tech API health`): `https://shosai.tech/v1/health` failed from outside — the edge, the API or the network; see «What is running».
- The Telegram bot, the chat and the heartbeat address come from `/root/shosai/.env` (`MONITORING_TELEGRAM_*`, `HEARTBEAT_PING_URL`): after a change run `render-env.py`, then `sudo -u deploy docker compose up -d --force-recreate alertmanager` here.

## Disk

Each release removes GHCR images other than the current and the previous one. Locally built images (`shosai-backend:*`, `shosai-edge:*` without `ghcr.io/`) are left alone; remove them by name once they are not in `.env` or `releases/previous.env`.
