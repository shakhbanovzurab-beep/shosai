# M2 — Cutover

Follow the common protocol in `docs/plan/prompts/README.md`. Load the four Docker skills — `docker-project-foundations`, `docker-build-strategies`, `docker-compose-patterns` and `docker-destructive-guardrails` — before starting.

## Goal

Switch `whisperer.one` from the draft to v2 in one night-time maintenance window of at most 30 minutes (nfr-12), with a tested way back.

## Before starting — ask the user

- The cutover date and time, and who is on duty.
- Confirmation that every slice is `done`, M1 rehearsals passed, and staging has run v2 without open incidents for an agreed period.

## Read first

- Target architecture §13 (resilience), §16 (observability), §17 (delivery), §20 (trade-offs), nfr-12.
- M1 results; F4 release procedure.

## Work

1. A step-by-step runbook in `docs/runbooks/cutover.md`: announcement, write freeze on the draft, final incremental migration, verification, DNS or edge switch of `whisperer.one` to v2, smoke tests, unfreeze.
2. Go/no-go criteria at each step, and the rollback procedure back to the draft with its time limit.
3. Checks that shipped native clients work against v2 in production: sign-in, live capture, meeting end, payment webhook, uploads.
4. A full rehearsal on staging with the same steps and timings.
5. After the user runs or approves the real cutover: watch SLOs and invariant monitors, and record the outcome.

## Definition of done

- The rehearsal fits the window and the rollback was exercised.
- The real cutover is executed only on the user's explicit command, not by the agent on its own.
