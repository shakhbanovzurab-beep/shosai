# D3 — Data inventory and mapping

Follow the common protocol in `docs/plan/prompts/README.md`. Load the skills `data-storage` and `consistency-coordination` before mapping: they are the method for keys, partitioning, replication and consistency decisions.

## Goal

Know where every piece of the draft's data goes in v2, so slices design their tables with migration in mind and M1 can move production data without loss.

## Inputs

- Draft models and migrations: `/root/whisperer/backend/src/meetassist/models/`, `features/*/`, `/root/whisperer/backend/alembic/`.
- Draft storage usage: S3 prefixes and what writes them.
- Draft Redis or Valkey keys that hold durable state.
- Target architecture: §6 (data placement and residency), §7 (tenancy), §8 (data model), §9 (invariants).
- Work only from code and migrations. Do not connect to any production database.

## Work

1. Build the draft schema as the last migration defines it: tables, columns, constraints, indexes, extensions, partitions.
2. Map every table and column to its v2 destination: slice, table, column, and transformation. Mark each as moved, transformed, derived (rebuilt, such as vectors), or dropped with a reason.
3. Apply the v2 ownership model: each row's home (RU or EU), personal or company scope, and what the directory holds.
4. Map S3 prefixes to v2 buckets and key layout.
5. Flag everything that can lose or corrupt data: money, entitlements, transcripts, audit, deletion state, tokens and sessions. For each, name the verification M1 must run.
6. Estimate volumes from the draft's code and design point; mark estimates as estimates.

## Output

- `docs/plan/DATA_MAPPING.md`.

## Definition of done

- Every draft table and S3 prefix appears in the mapping.
- Every dropped item has a reason; any drop of user data is listed for the user's decision.
- Every risky item has a named verification.
