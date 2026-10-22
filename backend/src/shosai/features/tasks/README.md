# tasks

The one place a person's work is tracked (SM-3): a task written by hand, an action item a meeting produced, a task a colleague assigned in a workspace, a Jira issue on a synced board and a hub's agreed work are the same row, and a change in any view — a Kanban card, Today, a workspace's Tasks screen, a meeting's page, Leo — is the same change everywhere. The slice owns boards with their columns and card order, where tasks sit on a person's boards, the projection of meetings' action items into tasks, workspace tasks under the one access policy, and the two-way Jira sync. The cabinet's feature is `kanban` (SLICE_MAP §4.3).

- Plan: [docs/plan/slices/tasks.md](../../../../../docs/plan/slices/tasks.md). Decisions: TK-D1…TK-D11 in the plan and [ADR 0059](../../../../../docs/adr/0059-tasks-one-store-boards-action-items-and-jira.md); TK-D12, the Kanban golden core, in [ADR 0060](../../../../../docs/adr/0060-kanban-golden-core.md).
- Public surface: `contracts` (`MeetingTasks`, `TaskReader`, `TaskIntake`, `BoardReader`, their types and errors) and `contracts.events` (`tasks.task.assigned`, `.due_changed`, `.completed`, `.reopened`, `.deleted`).

## Tables (each home, revision `b3d9e5a7c142`)

- `tasks` — the shareable resource `task` (company isolation): a meeting's task also opens to the meeting's readers and its assignee (the access policy's parent and named-reader rules, ADR 0059); the database keeps done with its moment, a member only on a workspace's task, a name only without one, one task per action item.
- `meeting_task_sets` — per meeting, the revision of its notes applied and whether a task of it was touched (TK-D3).
- `boards`, `board_columns`, `task_placements`, `task_settings` — personal (user isolation): a card sits in a column of its own board; column positions and card ranks are unique at commit.
- `application/account_data.py` — a person's personal tasks, sets, boards, columns, placements and settings are exported, copied (placements of personal tasks only) and erased; a workspace's tasks stay with it.

## Rules the domain holds

- `domain/tasks.py` — three statuses, an optional priority, where a task came from; a trimmed title of 1–200 characters, a Markdown description up to 10 000; a member does a workspace task, a name as written stands where no member is named; done exactly while `completed_at` is set; Today holds open personal tasks due on or before the day and those completed that day in the person's zone.
- `domain/changes.py` — a change by field presence: an absent field stays, `null` clears.
- `domain/ranks.py` — a card's place in its column is a fractional key: a move or an insert writes one key between its neighbours; a column whose keys grow past 48 characters is spaced again.
- `domain/boards.py` — ten icons, the `simple` and `project` templates, names and titles of 1–60 characters, 50 boards, 20 columns, 1 000 open cards, every kind of column kept; a layout only reorders and renames what the board shows, and a board that changed meanwhile is `board_changed`.
- `domain/placement.py` — a card shows in a column of its status: one whose status changed goes to the top of the first column of that status; a move to another kind sets the status; a board shows open cards and those done in the last 30 days; what comes to a person lands on their incoming board.
- `domain/action_items.py`, `domain/members.py` — every action item of a kept meeting is a task; a newer revision replaces a meeting's tasks only while none was touched; who does it is the meeting's owner, the name as written, or the one member of that name.
- `domain/jira.py` — status by Jira's category (never `undefined` → done), priority by the default scheme's ids (an unmapped one is never written), due days as calendar days, Atlassian Document Format as plain text.
