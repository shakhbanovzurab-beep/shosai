# ADR 0057 — Slice names follow the cabinet: `notes` keeps recorded meetings, `meetings` holds video calls

- **Status:** accepted by the owner on 2026-10-20, in the session of the former meetings plan's step 15.
- **Packages:** `notes` (the slice formerly `meetings`), `meetings` (the slice formerly `rooms`); capture, workspaces, calendar, agent, identity, billing, knowledge, hubs, commitments, tasks and memory, which name them; M1 and M2.
- **Context documents:** [SLICE_MAP](../plan/SLICE_MAP.md) §4.3, §7; [notes plan](../plan/slices/notes.md); [ADR 0038](0038-feature-slices-derived-from-the-product.md); [ADR 0056](0056-meetings-lifecycle-notes-and-share-links.md); CLAUDE.md "Architecture" (a backend and a frontend slice mirror each other by feature name).

## Context

The slice map named the slice that keeps recorded meetings — their transcript, Leo's write-up, the findings, the person's own notes, folders and the share link — `meetings`, and the slice of Shosai's own video calls `rooms`. To mirror the backend, its §4.3 asked the cabinet's `notes` feature (the Notes section, `/app/notes`) to become `meetings` and the cabinet's `meetings` feature (the Meetings section, `/app/meetings`) to become a page of it. That rename was derived by an agent from the mirror rule; the owner never asked for it.

The owner decided the other way round: the cabinet is the reference. Notes is where a person finds what was said and decided; Meetings is where a person holds a meeting — a new video call — or schedules one in the calendar.

## Decision

1. **The cabinet keeps its names.** `frontend/src/features/notes` (`/app/notes`, "Notes") and `frontend/src/features/meetings` (`/app/meetings`, "Meetings") are not renamed; SLICE_MAP §4.3 loses both rows.
   No other cabinet feature is renamed either (the owner, the same day): `file-manager`, `knowledge-base`, `kanban`, `workspace`, `leo`, `upgrade` and `download` keep their names beside the slices `files`, `knowledge`, `tasks`, `workspaces`, `agent`, `billing` and `releases`; SLICE_MAP §4.3 pairs them instead of renaming them.
2. **The backend slice `meetings` becomes `notes`** — code, documents and every name no client uses yet:

   | Before | After |
   |---|---|
   | `backend/src/shosai/features/meetings`, `tests/features/meetings`, `FeatureModule("meetings")` | `features/notes`, `tests/features/notes`, `FeatureModule("notes")` |
   | `docs/plan/slices/meetings.md`, decisions `MT-D*` | `docs/plan/slices/notes.md`, decisions keep their `MT-D*` ids |
   | `/v1/meetings/*`, `/v1/admin/users/{id}/meetings*`, OpenAPI tag `meetings` | `/v1/notes/*`, `/v1/admin/users/{id}/notes*`, tag `notes` |
   | events `meetings.meeting.ended`, `meetings.notes.ready`, `meetings.meeting.deleted`, `meetings.meeting.restored` | `notes.meeting.ended`, `notes.meeting.notes_ready`, `notes.meeting.deleted`, `notes.meeting.restored` |
   | ports, consumers, tasks, periodic jobs, rate limits, effect scopes, cursors `meetings.*` | `notes.*` |
   | Leo's toolset `meetings` and its tools `meetings.search`, `.get`, `.read_transcript`, `.list_findings` | toolset `notes`, tools `notes.search`, `.get`, `.read_transcript`, `.list_findings` |
   | AI calls' effect keys `meetings:{run}:{stage}:{part}` and cost features `meetings.<stage>` | `notes:{run}:{stage}:{part}`, `notes.<stage>` |
   | the account-data owner `meetings` | `notes` |
   | `MEETINGS_NOTES_MODEL`, `MEETINGS_NOTES_FALLBACK_MODEL`, `MEETINGS_TRANSCRIBE_MODEL`, `MEETINGS_TRANSCRIBE_FALLBACK_MODEL`, `MEETINGS_DIARIZE_MODEL`, `MEETINGS_MEDIA_SECONDS`, `MEETINGS_MEDIA_MEMORY_MB` | `NOTES_MODEL`, `NOTES_FALLBACK_MODEL`, `NOTES_TRANSCRIBE_MODEL`, `NOTES_TRANSCRIBE_FALLBACK_MODEL`, `NOTES_DIARIZE_MODEL`, `NOTES_MEDIA_SECONDS`, `NOTES_MEDIA_MEMORY_MB` |
   | metrics `shosai_meetings_*`, rule files `meetings.*.json` | `shosai_notes_*`, `notes.*.json` |

3. **What does not change.** The word "meeting" inside the slice (a note is a meeting's), the tables and SQL functions (`sessions`, `meeting_*`, `transcript_segments`, `meetings_shared_meeting`), the shareable resource kind `meeting` and the grants filed under it, the native routes (`/v1/sessions`, `/v1/me/sessions*`, `/v1/me/runs/{id}`), the share page (`/v1/shared/{token}`, `/s/{token}`), the queue `meeting`, Leo's provenance label `meeting:speech`, identity's audit actions `meetings_listed` and `meeting_restored`, billing's `billing.meeting_minutes`, the draft's contract baseline under `contracts/draft/` and the parity fixtures.
4. **Names kept in data move with the code.** One migration in every home renames the four event types in `outbox_messages`, the two consumers' marks in `processed_events`, the four periodic jobs in `schedule_runs`, the effect scopes in `effect_keys`, and the owner in identity's `account_deletions.erased_owners` and `home_transfers.copied_owners`, so nothing is delivered, run or erased twice; its downgrade renames them back. `provider_costs` is append-only money history and keeps the names it was written with; a cost report reads both prefixes for the rows written before.
5. **The slice `rooms` becomes `meetings`** and owns the cabinet's Meetings section: "New meeting" starts a Shosai video call, "Schedule in calendar" hands over to calendar, live meetings and joining; its recent recordings come from `notes`. "Upload a recording" is only in Notes: the Meetings menu loses it in the first frontend step of the `meetings` slice.

## Alternatives considered

| Alternative | Why not |
|---|---|
| Rename the cabinet's `notes` to `meetings` (SLICE_MAP §4.3 as it was) | The owner's product language is the cabinet's: Notes and Meetings are two sections with two purposes |
| Rename the backend folder only, keep `/v1/meetings` and the other public names | A slice whose routes, events and tools carry another slice's name confuses every reader; no client calls these names yet, so renaming now costs least |
| Keep the names kept in data and rename only the code | Consumers would apply recent events again, periodic jobs would start without their last run, erasures in progress would erase the slice again; one small migration avoids all of it |

## Consequences

- One rename commit while the cabinet still runs on sample data; the generated API types and the alert rules are regenerated in it.
- Staging's environment is rendered again with the `NOTES_*` names before the release that reads them.
- The plans that name either slice — SLICE_MAP, STATUS, REWRITE_PLAN, the other slices' plans, the target and Leo architectures, the runbooks — are updated in the same commit; earlier ADRs keep their wording as the record of their day.
