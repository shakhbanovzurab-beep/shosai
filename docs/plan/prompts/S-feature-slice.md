# S — Feature slice

Follow the common protocol in `docs/plan/prompts/README.md`. The slice name (one of [SLICE_MAP.md](../SLICE_MAP.md) §4.1, for example `identity`) is given in the launch line; below it is written `<name>`.

Load the skills before studying the draft, not before writing code — they shape the plan as much as the code:

- every slice: `fastapi` for the backend and the four Vercel skills for the frontend (CLAUDE.md "Mandatory skills");
- `site` (public site) also: the `seo` skill and the `seo-*` skills that `docs/seo/STRATEGY.md` §17 maps to the work at hand;
- the Leo slices (`agent`, `decisions`, `memory`, `proactive`, `errands`) and every slice that ships Leo tools: the `agent-architecture` skill and the [Leo architecture](../../design/leo/ARCHITECTURE.md) (CLAUDE.md "Mandatory skills");
- design questions inside a slice: the matching building-block skill (`api-design`, `data-storage`, `caching`, `messaging-streaming`, `task-scheduling`, `resilience-failure`, `consistency-coordination`), and `system-design` for decisions that change the target architecture;
- `python-doctor` and `react-doctor` when running the gates.

The slice plan lists which skills apply to each step; every implementation session loads them first.

## Goal

Build one capability of Shosai from scratch as a vertical slice, designed from the product — the new web UI in `frontend/`, the philosophy and the target and Leo architectures — and meeting every rule of CLAUDE.md. The draft is a reference to consult, not a behaviour to reproduce (CLAUDE.md "Goal"). Shipped native clients keep working: the native routes and frames the slice owns stay compatible.

## Session mode

A slice is too large for one session. Check STATUS.md and `docs/plan/slices/<name>.md`:

- **No slice plan yet → planning session.** Write the plan, do not write application code, and stop for the user's approval.
- **Plan approved → implementation session.** Implement the next unchecked step of the plan, verify it, tick it off, and stop. One step per session unless the step is small and the next one is tightly coupled.

## Planning session

1. Read the slice's card in `docs/plan/SLICE_MAP.md` §4.2 — scope, owned data, native and external routes, dependencies, events, Leo tools — its rows in the capability inventory (§2) and the contracts table (§3), and the owner's decisions in §8.1 that name it. Check in STATUS.md that its dependencies are `done`. `docs/plan/FEATURE_MAP.md` is the draft's inventory: use it to find the draft sources.
2. Study what the slice must serve: the screens, states and API calls of the new web UI in `frontend/` (its `api/` and `mocks/` layers show the shape it expects), and the native routes the slice owns in `contracts/`. Then consult the draft — backend modules, tests, specifications in `/root/whisperer/specs/`, data in `docs/plan/DATA_MAPPING.md` — for business rules and lessons worth keeping.
3. Read the target architecture sections that govern the slice: domain (§5), data (§6–§8), invariants (§9), interfaces (§10), flows (§11), async work (§12), resilience (§13), rules (§14).
4. Write `docs/plan/slices/<name>.md`:
   - **Scope:** capabilities, endpoints and frames (with their D1 compatibility class), screens and states (from the new web UI in `frontend/`; the draft's D2 inventory is a coverage list, ADR 0022), tasks and schedules.
   - **What is taken from the draft and why:** each business rule or lesson kept, with its source. A draft behaviour that is not taken needs no approval, unless a native client depends on it.
   - **Design:** contracts first — the slice's public interface, events, OpenAPI paths and WebSocket frames; tables and migrations per home; access control; invariants and how tests prove them.
   - **Steps:** ordered, each small enough for one session, each with its own checks. Typical order: contracts → data model and migrations → domain and application services → HTTP and WebSocket channels → tasks → frontend screens on the API → contract verification → staging check.
   - **Skills per step:** which skills each step loads.
   - **Decisions needed** from the user.
5. Set the slice to `planned` in STATUS.md once the user approves the plan.

## Implementation session

1. Take the first unchecked step of `docs/plan/slices/<name>.md`.
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
