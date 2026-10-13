# ADR 0038 — The feature slices are derived from the product, not from the draft's modules

- **Status:** accepted by the owner on 2026-10-13 (slice map, decisions SM-1…SM-15).
- **Packages:** every feature slice; F6 (email suppression and links, spend reports, step 10); M1 (DATA_MAPPING §5 regrouped).
- **Context documents:** [SLICE_MAP.md](../plan/SLICE_MAP.md); [CLAUDE.md](../../.claude/CLAUDE.md) "Philosophy", "Goal", "Architecture"; [ARCHITECTURE.md](../design/ARCHITECTURE.md) §5; [Leo architecture](../design/leo/ARCHITECTURE.md) §3.3; [FEATURE_MAP.md](../plan/FEATURE_MAP.md); [ADR 0002](0002-oauth-grants-outside-nango.md); [ADR 0022](0022-new-web-design-replaces-draft-parity.md); [ADR 0029](0029-leo-tools-owned-by-domain-slices.md).

## Context

- The slices S01–S17 were cut by D4 from the draft's backend modules (FEATURE_MAP). The owner has since decided that Shosai is built from scratch: the product is the new cabinet in `frontend/`, shaped by the philosophy and the target and Leo architectures; the draft is a reference only, and only the contracts of shipped native clients are preserved (CLAUDE.md "Goal").
- The old cut does not match the product. One slice held connectors, calendar and Jira; the context graph sat inside knowledge; the cabinet keeps tasks in three places and connects sources in two; studio's prompts and personal context had no owner; admin screens were one slice instead of belonging to the data they show.
- The slice map read every route, slice, `api/` and `mocks/` layer of the cabinet, the D1 contracts and both architectures, and derived the slices from what each screen needs and from what it takes off the user (remember, track, connect, watch, organise, coordinate).

## Decision

1. **25 slices replace S01–S17**, each one business capability named for what it does in Shosai: `identity`, `workspaces`, `billing`, `files`, `meetings`, `capture`, `knowledge`, `commitments`, `hubs`, `tasks`, `calendar`, `mail`, `connectors`, `agent`, `decisions`, `memory`, `proactive`, `errands`, `studio`, `mcp`, `support`, `releases`, `telemetry`, `rooms`, `site`. A slice owns its tables, `/v1` routes, events, Leo toolset and screens; backend `features/<name>/` and frontend `src/features/<name>/` carry the same name. The cards of SLICE_MAP §4.2 hold each slice's scope, data, native and external routes, dependencies, events and Leo tools.
2. **One owner per entity.** One task store in `tasks` (SM-3): the kanban card, the home "Today" list, workspace tasks, a meeting's action items and a linked Jira issue are views of the same task. One connection registry in `connectors` (SM-13). One plan catalogue in `billing`. One operator directory and fixed operator roles in `identity` (SM-12). Composition screens (home, Meetings overview, Settings dialog, admin dashboard) own no data.
3. **`studio` absorbs the Leo `models` slice** (SM-5): model catalogue, defaults and role assignments, platform and user prompts, personal context, behind the `ModelRoutes` and `PromptResolver` contracts that `agent`, `capture`, `meetings` and `memory` read. Skills stay in `agent`. Leo architecture §3.3 is amended.
4. **Kept, dropped and moved capabilities** (SLICE_MAP §8.1): rooms are mandatory and keep broadcasts and the room whiteboard; the satisfaction survey (`telemetry`) and newsletters (`support`) are kept, each with a screen designed in the new visual language before its frontend step; subtitles, the room AI panel, the onboarding tour, the top-bar ticker backend and the admin CRM and HR templates are dropped; referral and affiliate accrual stop at cutover and their records migrate as history (SM-9); email unsubscribe and suppression move to F6.
5. **Meeting-result push moves to `connectors` over Nango** (SM-11): it becomes Leo and meeting actions with approval; the own-OAuth integration apps retire and `meeting_integrations` is not migrated. This amends [ADR 0002](0002-oauth-grants-outside-nango.md) for meeting push only; calendars and Jira keep their own OAuth.
6. **Build order in four waves** (SLICE_MAP §5): 1 — record, remember, ask (identity, workspaces core, billing entitlements, files, meetings, capture, agent); 2 — track and connect (tasks, connectors, calendar, knowledge, commitments, hubs; decisions and memory in parallel); 3 — team and initiative (workspaces screens, billing payments, proactive, errands, mail, studio, mcp); 4 — operations and cutover readiness (support, releases, telemetry, rooms). `site` runs at any time after F6.
7. **The plan follows the cut.** REWRITE_PLAN §3 Phase 2 and §4, STATUS rows, DATA_MAPPING §5, ARCHITECTURE §5, the slice prompt and the F6 plan use the slice names. A slice's ID is its name; its plan is `docs/plan/slices/<name>.md`. FEATURE_MAP stays as the draft's inventory, superseded as the plan of record; SLICE_MAP §6.1 maps each old ID to the new slices.

## Consequences

- Four new slices come out of old ones (`commitments` from S07, `calendar` and `mail` from S12, `hubs` and `releases` from S16), `tasks` grows from S13 into the one task store, and `telemetry` merges S14's errors and analytics. Each is planned and built on its own.
- `workspaces` core (access policy, `resource_grants`, RLS, audit) moves to the start of wave 1, so every slice with shareable resources is written against it from its first step instead of being retrofitted.
- Frontend features are renamed in each owner's first frontend step (SLICE_MAP §4.3); URLs do not change.
- Users who set up a meeting-result push in the draft reconnect once; users with referral links stop earning rewards and must be told.
- Old IDs remain in accepted ADRs, the draft's captured contracts and the SEO strategy as historical references; SLICE_MAP §6.1 resolves them (S17 is `site`).

## Revisit when

- A slice turns out to change together with another one in most steps → merge them.
- A slice's tables or routes grow past what one team can hold, or one part needs a different scaling profile → split it along the seam that appeared.
- Hubs and workspace projects converge in use (SM-2) → a hub inside a workspace becomes a project; the shared topic engine in `commitments` keeps the data.
