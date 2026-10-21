# ADR 0060 — The Kanban golden core: fields, subtasks, comments, attachments, recurrence

- **Status:** accepted by the owner on 2026-10-21, with the plan of the Kanban golden core.
- **Packages:** `kanban-golden-core` (the cabinet's `kanban` slice on mocks), `tasks` (TK-D12, its steps 3, 4, 5 and 9), `files` (three additive contracts), `notes` (MT-D13, step 26), M1 (draft labels and column colours).
- **Context documents:** [Kanban golden-core plan](../plan/packages/KANBAN-golden-core.md) §2; [tasks plan](../plan/slices/tasks.md) TK-D12 and §3.8; [files plan](../plan/slices/files.md) FL-D4, FL-D6; [notes plan](../plan/slices/notes.md) MT-D13; [DATA_MAPPING](../plan/DATA_MAPPING.md) §5.8.

## Context

The cabinet's Kanban could not open a card: no description to edit, no subtasks, comments or attachments, a priority on every card, a free-text label, inert Filter and Sort buttons. On 2026-10-21 the owner set the golden core of a task board — what nearly every team uses — and left out automations, mirror and summary columns, time tracking, sprints, task types beyond state sets and backgrounds. The tasks plan had put subtasks, comments, attachments and labels outside the slice (§3.7) and dropped draft labels and column colours (TK-D7). The golden core needs a contract for all of them before the cabinet builds on mocks, so that `tasks` step 9 only swaps the data source.

## Decision

1. **The cabinet's mocks answer the `/v1` contract exactly** (paths, snake_case, ADR 0008 codes worded in the cabinet, cursor pages); `tasks` step 9 swaps them for the API.
2. **Subtasks are a checklist of their task** — a title and a tick, ordered, ≤ 100 — read and changed by whoever may read and change the task; never tasks of their own.
3. **Attachments are the task's own objects**, through files' upload flow with the purpose `task_attachment` (uploads ≤ 25 MiB, not in File Manager), counted in **the storage of the task's owner** — the person's for a personal task, the workspace's for a workspace task, whoever uploads them. **A File Manager file can be attached as a copy** that shares its stored object (FL-D4) and stays when the file is renamed or deleted. An image can be the card's cover through a preview.
4. **A field (sticker) belongs to the owner of its board**: the person on a personal board, the workspace on a workspace board; it is reused across that owner's boards and shown or hidden per board. **A field's value is part of the task**, seen by everyone who sees the task. The system fields — assignee, deadline, priority, recurrence — are the task's own; a new board shows assignee, deadline and priority. Custom fields are a set of states (each with a name and a palette colour), a number or a text. On screen a sticker is «поле» / "field".
5. **A recurring task comes back when it is done**: the next task is created at once, due on the schedule's next date after the original due day, skipping dates already past — never counted from the day it was completed. Daily, weekly on chosen days, monthly on a day.
6. **Priority may be empty**, and a new task has none.
7. **A Jira card carries Jira's fields only**; subtasks, comments, attachments, cover, recurrence and custom fields are not offered on a Jira board.
8. **A deleted column hands its cards to the first other column of its kind**; the last column of a kind cannot be deleted; the cabinet's Undo delays the call.
9. **Leo's marks are per field** — assignee, deadline, priority of a task Leo made from a meeting — with the meeting, moment and quote as the source, until the person changes that field. **Action-item findings get a priority** (notes MT-D13) so Leo can set it from the meeting.
10. **Draft labels and column colours are carried without loss**: a column colour to the nearest palette colour; a project's labels to a field «Labels» with one state per label; a task's first label becomes its value and the other labels are appended to its description as one line.

## Consequences

- The tasks plan gains §3.8: seven tables (subtasks, comments, attachments, stickers, their states, their place on boards, values), about twenty routes, a cover preview job, `starts_on`, `recurrence`, `leo_fields`, `recurred_from_id`, a nullable priority and a Markdown description. Its steps 3 and 4 build them; step 5 sets `leo_fields`; step 9 only swaps the cabinet's data source.
- Files adds, with tasks' step 3, the `task_attachment` purpose, the workspace reservation for it and the shared-object copy into an attachment, and moves an attachment's bytes to the workspace's storage when its task moves there.
- Notes adds `priority` to action-item findings (step 26), before tasks' step 5.
- A reader of a workspace task sees the definitions of the fields its values use, never the rest of their owner's fields or boards; the mechanism is tasks' step 2.
- Column sums are derived in the cabinet from the board's cards, not served; the filter lives in the URL and has no API.
- No notification comes from comments, attachments or subtasks; proactive may use them later.
- Boards of a workspace are not in any plan yet: fields carry their owner from the start, and the golden core builds personal boards. Planning workspace boards is a separate decision.

## Rejected

- **Subtasks as tasks** — Today, boards and Leo would see half-tasks, and one task store would hold two kinds of row.
- **Attachments as links to File Manager files** — a workspace task's attachment would depend on each uploader's sharing and membership.
- **Field values per person** (the plan's first proposal) — two readers of one task would see different estimates.
- **The next recurring task from the day the last one was completed** (the plan's first proposal) — the series would drift away from its schedule.
- **A served column total** — it would lag behind optimistic moves and ignore the filter.
