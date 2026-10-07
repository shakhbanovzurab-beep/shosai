# S — Feature slice

Follow the common protocol in `docs/plan/prompts/README.md`. The slice ID (S01–S17) is given in the launch line.

Load the skills before studying the draft, not before writing code — they shape the plan as much as the code:

- every slice: `fastapi` for the backend and the four Vercel skills for the frontend (CLAUDE.md "Mandatory skills");
- S17 (public site) also: the `seo` skill and the `seo-*` skills that `docs/seo/STRATEGY.md` §17 maps to the work at hand;
- design questions inside a slice: the matching building-block skill (`api-design`, `data-storage`, `caching`, `messaging-streaming`, `task-scheduling`, `resilience-failure`, `consistency-coordination`), and `system-design` for decisions that change the target architecture;
- `python-doctor` and `react-doctor` when running the gates.

The slice plan lists which skills apply to each step; every implementation session loads them first.

## Goal

Rewrite one feature of the draft into v2 as a vertical slice, so that users see no difference, native clients keep working, and the slice meets every rule of CLAUDE.md and the target architecture.

## Session mode

A slice is too large for one session. Check STATUS.md and `docs/plan/slices/<ID>.md`:

- **No slice plan yet → planning session.** Write the plan, do not write application code, and stop for the user's approval.
- **Plan approved → implementation session.** Implement the next unchecked step of the plan, verify it, tick it off, and stop. One step per session unless the step is small and the next one is tightly coupled.

## Planning session

1. Read the slice's row in `docs/plan/REWRITE_PLAN.md` §3 and, if it exists, `docs/plan/FEATURE_MAP.md`.
2. Study the draft sources of the slice: backend modules, frontend features, tests, specifications in `/root/whisperer/specs/`, and its data in `docs/plan/DATA_MAPPING.md`.
3. Read the target architecture sections that govern the slice: domain (§5), data (§6–§8), invariants (§9), interfaces (§10), flows (§11), async work (§12), resilience (§13), rules (§14).
4. Write `docs/plan/slices/<ID>.md`:
   - **Scope:** capabilities, endpoints and frames (with their D1 compatibility class), screens and states (from the new web UI in `frontend/`; the draft's D2 inventory is a coverage list, ADR 0022), tasks and schedules.
   - **Differences from the draft's behaviour** demanded by CLAUDE.md, the target architecture or the new web UI, each with its user-visible effect. A behaviour the new UI does not show needs the user's approval to be dropped.
   - **Design:** contracts first — the slice's public interface, events, OpenAPI paths and WebSocket frames; tables and migrations per home; access control; invariants and how tests prove them.
   - **Steps:** ordered, each small enough for one session, each with its own checks. Typical order: contracts → data model and migrations → domain and application services → HTTP and WebSocket channels → tasks → frontend screens on the API → contract verification → staging check.
   - **Skills per step:** which skills each step loads.
   - **Decisions needed** from the user.
5. Set the slice to `planned` in STATUS.md once the user approves the plan.

## Implementation session

1. Take the first unchecked step of `docs/plan/slices/<ID>.md`.
2. Implement it under all CLAUDE.md rules: feature-first slice, contracts between slices, file length limits, strong typing, model-facing text in English, telemetry per `docs/observability.md` if it exists.
3. Tests ship with the step: domain tests, invariant tests, access-isolation tests for every read path that touches company data, and contract snapshot updates.
4. Verify:
   - CLAUDE.md checks for the zones you changed, including the 100/100 gates;
   - contract compatibility with `contracts/draft/` for the endpoints and frames of this step — anything a native client uses must stay compatible;
   - the screens of this step look and behave as in the new web UI, now on real data;
   - on https://one.whisperer.one once F4 is done.
5. Tick the step off in the slice plan, update STATUS.md (`in progress`, or `done` after the last step), report and wait for «Принято».

## Definition of done for the whole slice

- Every capability in the slice plan works; every step is ticked off.
- Contract compatibility: no endpoint or frame used by native clients or external integrations is missing or changed incompatibly.
- Screens: the slice's screens of the new web UI work on the API, with no sample or mock data left for them.
- Gates 100/100, mypy strict, tests and CI green; staging checked when F4 is available.
