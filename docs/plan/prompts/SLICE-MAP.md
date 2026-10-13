# Slice map — derive the feature slices from the cabinet and the philosophy

Follow the common protocol in `docs/plan/prompts/README.md`. **Planning only: no application code.** The session may run in parallel with the F1 audit; they touch different files.

## Why

The slices S01–S17 in `docs/plan/REWRITE_PLAN.md` §3 and `docs/plan/STATUS.md` were cut from the draft's modules (`docs/plan/FEATURE_MAP.md`, D4). The owner has since decided that Shosai is built from scratch (CLAUDE.md "Goal"): the product is the new cabinet in `frontend/`, shaped by the philosophy (CLAUDE.md "Philosophy"), the target architecture and the Leo architecture. The draft is a reference only. The slices must be derived again from the product, not from the draft.

## Load first

The four frontend skills (CLAUDE.md "Mandatory skills") before reading `frontend/`; `fastapi`; `agent-architecture` (Leo zone); `requirements-scoping`, `service-decomposition` and `api-design` for the cut and the contracts.

## Read

- CLAUDE.md in full, especially "Philosophy" and "Goal".
- `docs/design/ARCHITECTURE.md` §5–§12 and §14; `docs/design/leo/ARCHITECTURE.md` in full.
- `frontend/`: every route in `src/app/routes/`, every slice in `src/features/` (user panel and `admin-*`), their `api/` and `mocks/` layers — the mocks show the data and calls each screen expects.
- `contracts/`: the native routes and frames (nfr-12) and the external integrations' callbacks — the only draft contract that must survive.
- `docs/plan/REWRITE_PLAN.md`, `STATUS.md`, `FEATURE_MAP.md`, `DATA_MAPPING.md` — the current cut and what the migration needs.

## Work

1. **Capability inventory.** Walk every screen and state of the cabinet and list what it needs from the backend: capabilities, data, calls, realtime, background work, Leo's part. Mark what each capability does for the user in the philosophy's terms (remember, track, connect, watch, organise, coordinate), and flag anything that adds load instead of removing it.
2. **Native and external contracts.** Map each native route and frame and each external callback to the capability that will own it.
3. **The cut.** Group capabilities into slices by business capability (CLAUDE.md "Architecture"): each slice owns its data, contracts and screens, and integrates with others only through contracts, events and shared context. Leo's tools live in the slices that own the data (ADR 0029). Name each slice for what it does in Shosai, not for a draft module.
4. **Order.** Dependencies between slices and a build order that gives the user a working Shosai as early as possible: the smallest set of slices that makes the cabinet usable end to end first, then the rest by value.
5. **Compare** with the current S01–S17: what merges, splits, disappears or is new, and what the platform package F6 must provide for the new cut.

## Output

Write `docs/plan/SLICE_MAP.md`: the capability inventory (screen → capability → slice), the slices with their scope, owned data, native routes, dependencies and Leo tools, the build order, and the comparison with the old cut. List the decisions the owner must take, each with a proposed answer and its trade-off.

After the owner approves it, in the same session and as a separate step: rewrite REWRITE_PLAN.md §3 Phase 2 and §4, replace the slice rows in STATUS.md, mark FEATURE_MAP.md as the draft's inventory (a reference, superseded as the plan of record by SLICE_MAP.md), and record the cut as an ADR. Report, list the skills you loaded, and wait for «Принято».
