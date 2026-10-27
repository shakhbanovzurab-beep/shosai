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

In GitHub, open the commit's Release run and choose "Re-run all jobs". Only the head of `main` is released: a re-run of an older commit skips itself.

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

The same holds for `NOTES_TRANSCRIBE_MODEL` (notes plan step 9a): the OpenRouter model that transcribes imported recordings with timed segments. `render-env.py` writes `openai/whisper-large-v3` (priced per second of audio by revision `d5e2a7c9f4b1`), or the owner's `NOTES_TRANSCRIBE_MODEL` and `NOTES_TRANSCRIBE_FALLBACK_MODEL` when set. `NOTES_MEDIA_SECONDS` (300) and `NOTES_MEDIA_MEMORY_MB` (1024) bound each `ffprobe` and `ffmpeg` call; the defaults need no entry. Likewise `NOTES_DIARIZE_MODEL` (step 10): pyannote's model for the speakers of recordings; `render-env.py` writes `precision-3` (priced per second by revision `b7e2f05c9d18`), or the owner's value when set.

**Recordings without speakers.** When pyannote refuses its key — 402 Payment Required when the account has no credit, seen on 2026-10-21 (notes plan step 21) — the workers-meeting log shows `"provider": "pyannote", "status": 402` three times and the diarize stage fails with `provider_error`; the run ends `partially_completed`, the transcript and Leo's notes are there, the lines carry no speaker. Top up the pyannote account or replace `PYANNOTE_API_KEY` by «Change a setting or a secret»; runs already done keep their lines without speakers.

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

Check, as the migrator: `SELECT extversion FROM pg_extension WHERE extname = 'vector';` returns a version, and `SELECT '[1,2]'::halfvec(2);` succeeds. Then release the commit again ([Release a commit again](#release-a-commit-again)). Not yet done on the staging homes: releases from `f25187da` (2026-10-27 14:40 UTC) on rolled back on this error.

## TLS certificate

`shosai-certificate.timer` renews it twice a day. Check: `systemctl list-timers shosai-certificate.timer` and `journalctl -u shosai-certificate.service`. Renew by hand: `sh /srv/shosai/deploy/certificate.sh renew /srv/shosai`.

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
