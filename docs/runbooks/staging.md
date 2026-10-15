# Runbook — staging on shosai.tech

What to do when staging needs a hand. How staging is built: [deploy/staging/README.md](../../deploy/staging/README.md); why: [ADR 0050](../adr/0050-staging-release-from-ci.md). Commands run as root on the staging host unless noted; the plane is the Compose project in `/srv/shosai`.

## What is running

```bash
cd /srv/shosai
grep IMAGE .env                      # the images of the running release
tail -n 5 releases/history.log       # time, result (released, rolled-back, failed), backend, edge
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

## TLS certificate

`shosai-certificate.timer` renews it twice a day. Check: `systemctl list-timers shosai-certificate.timer` and `journalctl -u shosai-certificate.service`. Renew by hand: `sh /srv/shosai/deploy/certificate.sh renew /srv/shosai`.

## Disk

Each release removes GHCR images other than the current and the previous one. Locally built images (`shosai-backend:*`, `shosai-edge:*` without `ghcr.io/`) are left alone; remove them by name once they are not in `.env` or `releases/previous.env`.
