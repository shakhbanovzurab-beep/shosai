# D4 — Feature map

Follow the common protocol in `docs/plan/prompts/README.md`.

## Goal

Make sure every capability of the draft has an owner in v2, and that nothing is dropped silently. The initial slice table in `docs/plan/REWRITE_PLAN.md` §3 is a starting point; this package makes it complete and exact.

## Inputs

- Draft backend: `/root/whisperer/backend/src/meetassist/` — `features/`, `services/`, `api/`, `tasks/`, top-level modules.
- Draft frontend: `/root/whisperer/frontend/src/features/`, `app/`, `shared/`.
- Draft specifications: `/root/whisperer/specs/` and `/root/whisperer/docs/`.
- Target architecture: §1 (product scope), §5 (domains), §21 (out of scope).

## Work

1. List every draft backend module and frontend feature with its purpose, entry points (routes, frames, tasks, schedules) and size.
2. Assign each to one v2 slice (S01–S17) and one v2 domain from target architecture §5.
3. Mark what the draft has but the target architecture does not mention, and what the target architecture requires but the draft lacks (for example companies, two data homes, room track transcription).
4. For modules with no v2 place (for example Temporal or NATS usage, `demo`, `whiteboard`, `hub`), propose keep, merge or drop, with the user-visible consequence. The user decides; do not decide alone.
5. Mark cross-slice dependencies: which slice calls which, through which contract.
6. Update the slice table in `REWRITE_PLAN.md` §3 and the rows in `STATUS.md` to match.

## Output

- `docs/plan/FEATURE_MAP.md`; updated `REWRITE_PLAN.md` §3 and `STATUS.md`.

## Definition of done

- Every draft module and frontend feature is assigned or listed for a decision.
- The user has decided every keep, merge or drop question; decisions are recorded in `FEATURE_MAP.md`.
