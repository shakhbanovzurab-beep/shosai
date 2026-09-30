# M1 — Data migration

Follow the common protocol in `docs/plan/prompts/README.md`.

## Goal

Move the draft's production data into v2 without losing or corrupting anything, with a proven, repeatable procedure that fits the cutover window.

## Before starting — ask the user

- Read access to a **copy** of the production database and storage. Never the live production systems.
- Where the copy and the migration runs may live, and who may see the data.

## Read first

- `docs/plan/DATA_MAPPING.md` (D3), every slice's data model, target architecture §6–§9, §13.3, nfr-12, nfr-13.

## Work

1. Migration tooling that reads the draft schema and writes the v2 schema per `DATA_MAPPING.md`: assigns each account and company to its home, fills the directory, transforms what the mapping transforms, and rebuilds derived stores (Qdrant) from sources.
2. Idempotent and resumable: rerunning a step after a failure gives the same result.
3. Verification after every run: row counts per mapped table, money totals and entitlements, transcript sequences, audit continuity, deletion state, file objects against pointers. Any mismatch fails the run.
4. Rehearse on the copy until two consecutive runs pass verification; measure the duration against the 30-minute window of nfr-12, and design an incremental catch-up if a full run does not fit.

## Definition of done

- Two consecutive rehearsals pass every verification.
- The measured duration fits the cutover plan agreed with the user.
- No production system was written to.
