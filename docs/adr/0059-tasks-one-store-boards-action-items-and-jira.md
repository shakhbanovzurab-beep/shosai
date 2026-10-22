# ADR 0059 — Tasks: one store, boards, meetings' action items and Jira

- **Status:** accepted by the owner on 2026-10-22 (tasks slice plan, decisions TK-D1…TK-D11 as written). TK-D12, the Kanban golden core, is [ADR 0060](0060-kanban-golden-core.md) (2026-10-21).
- **Packages:** `tasks` (owner); workspaces (the access policy's parent and named-reader rules, `MembershipReader.members`, `ProjectReader`, no `/v1/workspaces/{id}/tasks`), notes (action items, the native action-item route, `FindingFacts`), connectors (the Jira grant and its OAuth callback), proactive (the five events), hubs (boards, `TaskIntake`), M1 (draft tracker data and action items), M2 (the action-item route).
- **Context documents:** [tasks plan](../plan/slices/tasks.md) §2; [ARCHITECTURE.md](../design/ARCHITECTURE.md) §7, §8.2, §10, §12, §14 rules 1, 12, 14; [Leo architecture](../design/leo/ARCHITECTURE.md) §7.4, §8, §9.3; [SLICE_MAP](../plan/SLICE_MAP.md) §3, §4.2.10, §4.2.13, SM-3, SM-13; [DATA_MAPPING](../plan/DATA_MAPPING.md) §5.4, §5.8; ADR 0002, 0039, 0053, 0056, 0058.

## Context

The cabinet kept three task lists — Kanban cards, workspace tasks, the home's local "Today" — and two checkbox systems for meetings' action items; the owner decided one source of truth (SM-3). The draft's tracker had no assignee, a 5 000-card unpaginated board and dense positions that raced; it deleted and re-inserted action items on every regeneration, losing ticks; its Jira link never pushed local edits after the first pass, advanced its watermark past failed pages, matched priorities by name and trusted only the link id in the webhook's path. The target architecture listed no tasks among the resources with workspace access, and the workspaces plan put workspace tasks behind a dependency that waits for billing's payments.

## Decision

1. **One task API (TK-D1).** `/v1/tasks` serves every space: a workspace's screen lists `?workspace_id=` and creates with `workspace_id`; `?assignee=me` replaces the cabinet's `/me/tasks`. Boards are at `/v1/boards`, a card addressed by its task's id. There is no `/v1/workspaces/{id}/tasks`.
2. **Who sees a workspace task (TK-D2).** Tasks are a shareable resource `task` under the one access policy, which learns two additive rules: a row also opens to whoever may read its *parent* row now, and to the active member its *named reader* column names. A hand-made workspace task is `organization`; a meeting's task is `owner`, read by its owner, its assignee and whoever may read the meeting. Admins read only what they could otherwise. Whoever reads a workspace task may change it; its owner and the workspace's admins may delete it. Personal tasks are their owner's alone.
3. **Action items are tasks (TK-D3).** Every action item of a kept meeting is a task of the meeting's owner in the meeting's space, keyed by its finding. A newer revision of the notes replaces a meeting's tasks only while the person has touched none of them. Who does it is the owner (their own voice), the name as written, or the one workspace member of that name. A personal meeting shared into a workspace takes its tasks there; a deleted meeting takes its untouched open tasks with it; draft action items are carried with their done state and their draft id.
4. **One incoming board (TK-D4).** Tasks assigned to the person in a workspace and their own meetings' open action items land on the board they chose, at the top of the first column of their kind, when it is read. Nothing lands until a board is chosen; a Jira board cannot be chosen.
5. **Board bounds (TK-D5).** A board shows its open cards (≤ 1 000) and those done in the last 30 days; 50 boards per person, 20 columns per board, every kind kept.
6. **Deletion (TK-D6).** A task is deleted at once (the cabinet's Undo delays the call). Deleting a board removes its placements and its hand-made personal tasks; a Jira board's deletion stops the sync and removes its mirrored tasks, nothing in Jira.
7. **Draft tracker data (TK-D7, revised by TK-D12).** Projects become boards, statuses columns, tasks keep their fields (`urgent` → `high`, `due_at` → the day in the owner's zone); keys, archive flags and positions are not carried; labels and column colours are carried as ADR 0060 says.
8. **Jira (TK-D8).** The grant, its rotating refresh token and `GET /v1/jira/oauth/callback` are connectors'; tasks owns links, the sync and `POST /v1/jira/webhook/{link_id}`. Draft links are not carried: their boards and tasks are, with each task's Jira key as a link, and the person syncs once more. Jira works on every plan. Changes made in Shosai go to Jira at once (409 with Jira's reason); webhooks, checked by Atlassian's signature and the unguessable link id, accelerate a 15-minute sweep through due rows; status maps by category, priority by the default scheme's ids. Personal Data Reporting answers for the Atlassian accounts stored.
9. **Leo's label for task text (TK-D9).** A new provenance label `task:foreign`: text in tasks the person did not write; the read tools declare it.
10. **Events (TK-D10).** `tasks.task.assigned`, `.due_changed`, `.completed`, `.reopened`, `.deleted` — ids, codes and the due day only.
11. **Today (TK-D11).** The person's open personal tasks due on or before their day, and those completed that day; overdue ones stay until done or moved; the day is the profile's zone.

## Alternatives considered

| Alternative | Why not |
|---|---|
| `/v1/workspaces/{id}/tasks` beside `/v1/tasks` | Two contracts for one store, and a wait for billing's payments before any workspace task exists |
| Copy a meeting's audience into the task's grants | A copy of access rights is a cache that lags a share change (§7: never cached) and makes every assignment an access change |
| Replace a meeting's tasks on every revision, merging by text | Matching words is language-dependent and still duplicates or loses ticks |
| Every action item on a board by default | Fills Kanban with work the person never chose; the incoming board is the person's choice |
| Carry draft Jira links with their ids verbatim | The draft linked projects, the cabinet links boards; a migrated link would need Jira's API per user at cutover |
| Priority by name, as the draft | Priority names are site-configured and localised; the default scheme's ids are the same everywhere |

## Consequences

- Workspaces' policy gains the parent and named-reader rules with their isolation-kit cases (tasks step 2); its contracts gain `MembershipReader.members` and `ProjectReader` (step 3).
- Notes' `FindingFacts` gains `owner_is_meeting_owner` and the revision of the findings (step 5); notes' step 22 serves the native action-item route through `MeetingTasks`.
- §7 of the architecture, Leo §7.4 and §9.3, SLICE_MAP §3, §4.2.10 and §4.2.13, the workspaces plan, DATA_MAPPING §5.4 and §5.8 and the notes plan were amended with the approval.
- Draft users of the Jira link re-link once; their draft webhooks expire within 30 days.

## Revisit when

- Meetings yield so many action items that the meeting page or the incoming board fills with noise (measured in tasks step 18).
- Workspace boards are planned (an open point of ADR 0060).
