# ADR 0050 — Staging is released from CI over a single-command SSH key; its secrets stay on the host

- **Status:** accepted by the owner on 2026-10-15 (secrets on the host instead of the GitHub environment; GitHub holds the deploy key, the host's public key and the cabinet's build variables).
- **Package:** F4, step 4; revises F4-D4 and records F4-D1 and the release path.
- **Context documents:** [ARCHITECTURE.md](../design/ARCHITECTURE.md) §17 (delivery); [F4 plan](../plan/packages/F4-delivery-staging.md) F4-D1, F4-D4; [ADR 0040](0040-shosai-tech-is-the-domain.md).

## Context

- F4-D1 put staging on the development machine behind a `deploy` user, reached by GitHub Actions over SSH with a key restricted to one forced command.
- F4-D4 planned to keep staging's secrets (about 40) in the GitHub environment `staging`, written to the host on every release.
- Step 3 already renders every staging secret on the host from the owner's `.env` (`deploy/staging/render-env.py`), and generates staging's own (Valkey and cache ACLs, Qdrant's key, the admin sign-in segment). Copying them into GitHub would keep two sources of the same values and send every one of them over SSH on each release.

## Decision

1. **Secrets stay on the host.** `render-env.py` remains their only source; a release never carries an application secret. Rotating one is an edit of the owner's `.env`, `render-env.py` and a restart of the affected role.
2. **GitHub holds four values,** all in the environment `staging`: the secret `STAGING_SSH_KEY` (the deploy key's private part), the secret `CABINET_ENV` (the cabinet's build variables, including the admin sign-in path), and the variables `STAGING_SSH_HOST` and `STAGING_SSH_KNOWN_HOSTS` (the host's public ed25519 key, so the job refuses any other host).
3. **The workflow.** `.github/workflows/release.yml` runs when CI completes on a push to `main`, only if CI passed and the commit is still the head of `main` (a slower run of an older commit never replaces a newer release). It builds the backend and edge images of that commit, pushes them to GHCR as `shosai-<image>:<commit>` and deploys them by digest. Releases never run in parallel and are never cancelled midway.
4. **One command per key.** The key's `authorized_keys` line is `restrict,command="/srv/shosai/deploy/release.sh"`: no shell, no forwarding. `release.sh` accepts only `release <actor> <backend> <edge>`, where each image is from the repository's GHCR namespace, with a 40-character commit tag and a digest, both from the same commit.
5. **No stored registry credential.** The deploy job's own token (`packages: read`) reaches `release.sh` on stdin, lives in a temporary Docker config for the two pulls and expires with the job.
6. **Release order of §17.** Migrations of both homes, then task consumers and the scheduler, then `api`, `ws` and the edge, each waiting until healthy; then `/v1/health` through the edge. If any step fails, the previous images return and the release fails; migrations stay, being expand-only. `releases/previous.env` and `releases/history.log` record each release; GHCR images other than the current and the previous release are removed from the host.

## Consequences

- A leaked deploy key can only redeploy images of this repository that GHCR already holds; it cannot read secrets or run commands.
- GitHub cannot show or audit staging's application secrets; whoever has root on the host can. This is accepted for staging only (F4-D1); production gets its own host and secret handling (§17).
- Changing an application secret no longer needs a GitHub edit; changing the cabinet's build variables needs both `CABINET_ENV` and a release.

## Revisit when

- Production delivery is designed, or staging moves off the development machine.
