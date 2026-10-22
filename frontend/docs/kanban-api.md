# Kanban API

The contract between the Kanban screen (`/app/kanban`) and the backend's `tasks` slice: the `/v1` routes of the
[tasks plan](../../docs/plan/slices/tasks.md) §3.3, the golden core's TK-D12 (§3.8,
[ADR 0060](../../docs/adr/0060-kanban-golden-core.md)) and time on a task (§3.9,
[ADR 0061](../../docs/adr/0061-kanban-time.md)). Until `tasks` serves them, `npm run dev` answers exactly these
routes from `src/features/kanban/mocks/` (KG-D1); `tasks` step 9 points `api/` at the generated client and deletes
the mocks. The shapes are in `src/features/kanban/domain/{boards,tasks,stickers,time}-contract.ts`; refusals are the
platform's envelope `{error: {code, request_id, params?}}` (ADR 0008), worded by the cabinet from
`domain/problems.ts`. Snake_case; calendar days are `"2026-10-21"`.

The Kanban package moves the screens from the old sample paths `/api/kanban/*` to these routes in its step 2
([plan](../../docs/plan/packages/KANBAN-golden-core.md)).

## Boards, columns, cards

| Method   | Path                                       | Body                                              | Response                 |
| -------- | ------------------------------------------ | ------------------------------------------------- | ------------------------ |
| `GET`    | `/v1/boards`                               | —                                                 | `BoardsResponse`         |
| `POST`   | `/v1/boards`                               | `{name, icon, template}`                          | `201 BoardSummary`       |
| `PUT`    | `/v1/boards/incoming`                      | `{board_id \| null}`                              | `BoardsResponse`         |
| `GET`    | `/v1/boards/{id}`                          | —                                                 | `BoardDetail`            |
| `PATCH`  | `/v1/boards/{id}`                          | `{name?, icon?}`                                  | `BoardSummary`           |
| `DELETE` | `/v1/boards/{id}`                          | —                                                 | `204`                    |
| `PUT`    | `/v1/boards/{id}/layout`                   | `{columns: [{id, title, task_ids}]}`              | `204`                    |
| `POST`   | `/v1/boards/{id}/columns`                  | `{title, kind, position, color?}`                 | `201 ColumnHead`         |
| `PATCH`  | `/v1/boards/{id}/columns/{column_id}`      | `{title?, color?, collapsed?, position?}`         | `ColumnHead`             |
| `DELETE` | `/v1/boards/{id}/columns/{column_id}`      | —                                                 | `204`                    |
| `POST`   | `/v1/boards/{id}/cards`                    | `{title, column_id, position, copy_of?}`          | `201 Card`               |
| `PATCH`  | `/v1/boards/{id}/cards/{task_id}`          | `{title?, priority?, column_id?, position?}`      | `Card`                   |
| `POST`   | `/v1/boards/{id}/sync`                     | —                                                 | `BoardSummary` (Jira)    |
| `GET`    | `/v1/boards/jira/available`                | —                                                 | `JiraAvailable`          |
| `POST`   | `/v1/boards/jira`                          | `{site, board_id}`                                | `201 BoardSummary`       |

- A board holds its open cards and those done in the last 30 days (TK-D5): at most 1 000 open (`board_full`),
  50 boards (`boards_full`), 20 columns (`board_columns_full`). `revision` goes up with every change.
- A card is a task; its id is the task's. Moving sends `column_id` and `position` together; a column of another
  kind changes the task's status. A card whose status changed elsewhere is put at the top of the first column of
  its kind when the board is read.
- Deleting a column moves its cards to the top of the first other column of its kind, in their order; the last
  column of a kind stays (`last_column_of_kind`). The screen hides it at once and sends `DELETE` when the Undo
  toast closes.
- The incoming board (TK-D4) receives the tasks assigned to the person in workspaces and the tasks of their
  meetings that are open and on none of their boards; nothing lands until one is chosen; a Jira board cannot be
  one (`jira_not_incoming`).
- Jira boards: columns and deletes are Jira's (`managed_in_jira`); changes wait for the first sync
  (`first_sync`) and a working connection (`reconnect_jira`); `sync_error` is a code. Colour and collapse of a
  column are display only and allowed.

## Tasks

| Method   | Path                                                     | Body                                      | Response            |
| -------- | -------------------------------------------------------- | ----------------------------------------- | ------------------- |
| `GET`    | `/v1/tasks/{id}`                                         | —                                         | `TaskDetail`        |
| `PATCH`  | `/v1/tasks/{id}`                                         | `TaskPatch` (field presence, `null` clears)| `TaskDetail`        |
| `DELETE` | `/v1/tasks/{id}`                                         | —                                         | `204`               |
| `POST`   | `/v1/tasks/delete`                                       | `{task_ids}` (1–500, all or none)         | `204`               |
| `POST`   | `/v1/tasks/{id}/subtasks`                                | `{title, position?}`                      | `201 Subtask`       |
| `PATCH`  | `/v1/tasks/{id}/subtasks/{subtask_id}`                   | `{title?, done?, position?}`              | `Subtask`           |
| `DELETE` | `/v1/tasks/{id}/subtasks/{subtask_id}`                   | —                                         | `204`               |
| `GET`    | `/v1/tasks/{id}/comments?cursor&limit`                   | —                                         | `CommentsPage`      |
| `POST`   | `/v1/tasks/{id}/comments`                                | `{body}`, optional `Idempotency-Key`      | `201 Comment`       |
| `PATCH`  | `/v1/tasks/{id}/comments/{comment_id}`                   | `{body}` (the author only)                | `Comment`           |
| `DELETE` | `/v1/tasks/{id}/comments/{comment_id}`                   | —                                         | `204`               |
| `POST`   | `/v1/tasks/{id}/attachments`                             | `{upload_id}` or `{file_id}`              | `201 Attachment`    |
| `GET`    | `/v1/tasks/{id}/attachments/{attachment_id}/download`    | —                                         | `{url, expires_at}` |
| `DELETE` | `/v1/tasks/{id}/attachments/{attachment_id}`             | —                                         | `204`               |
| `PUT`    | `/v1/tasks/{id}/values/{sticker_id}`                     | `{state_id}` \| `{number}` \| `{text}`    | the value           |
| `DELETE` | `/v1/tasks/{id}/values/{sticker_id}`                     | —                                         | `204`               |

- `starts_on` needs `due_on` and is not after it (`range_invalid`). A recurrence on a task without a due day gives
  it the first date from today. Marking a recurring task done creates the next one, due on the schedule's next
  date after the original due day, skipping past dates (KG-D5).
- A person's change of the assignee, the due day or the priority removes that field from `leo_fields` (KG-D10).
- Attachments are uploaded through `src/lib/uploads/` with the purpose `task_attachment` (≤ 25 MiB; `workspace_id`
  for a workspace task) and claimed by `upload_id`, or copied from a File Manager file by `file_id` (FL-D4). They
  count in the task owner's storage. Only an image can be the cover (`cover_not_image`).
- Comments are plain text, ≤ 5 000 characters, newest first by an opaque cursor keyed on the last comment
  returned, so a comment written meanwhile repeats nothing; another person's comment answers `not_comment_author`.
- A Jira task has no subtasks, comments, attachments, cover, recurrence, range or custom fields
  (`jira_unsupported`, KG-D8).

## Fields (stickers)

| Method   | Path                                          | Body                                            | Response              |
| -------- | --------------------------------------------- | ----------------------------------------------- | --------------------- |
| `GET`    | `/v1/stickers`                                | —                                               | `StickersResponse`    |
| `PATCH`  | `/v1/stickers/{id}`                           | `{name?, states?}` (the full list of states)    | `CustomSticker`       |
| `DELETE` | `/v1/stickers/{id}`                           | —                                               | `204`                 |
| `POST`   | `/v1/boards/{id}/stickers`                    | `{sticker_id}` or `{kind, name, states?}`       | `201 BoardSticker`    |
| `PATCH`  | `/v1/boards/{id}/stickers/{sticker_id}`       | `{visible}`                                     | `BoardSticker`        |
| `DELETE` | `/v1/boards/{id}/stickers/{sticker_id}`       | —                                               | `204`                 |

- System fields `assignee`, `due`, `priority`, `recurrence` are on every board; a new board shows the first three.
  They can be shown or hidden, never removed (`system_sticker`).
- A custom field — a set of states (≤ 20, each with a palette colour), a number or a text — belongs to its board's
  owner and is reused on the owner's other boards; ≤ 20 per board, ≤ 100 per owner. Its value is part of the task:
  a value of a field that is not on the reader's board comes in `TaskDetail.other_values`.
- Editing a set keeps the values of the states it keeps; a state left out clears the values that used it.
- `GET /v1/stickers` gives each field its boards and `usage`: how many tasks carry a value of it, in all and per
  state, so removing a state or deleting the field can say what it clears.
- `stopwatch`, `timer` and `time_tracking` are system fields too, hidden on a new board and never on a Jira board
  (`jira_unsupported`). The stopwatch's `BoardSticker` carries `automations`, changed with
  `PATCH /v1/boards/{id}/stickers/stopwatch {automations}` (see Time).
- Palette: `gray, red, orange, amber, green, teal, blue, violet, pink`.
- Column sums (Σ) are not served: the screen sums the cards it shows.

## Time

| Method   | Path                                   | Body             | Response                     |
| -------- | -------------------------------------- | ---------------- | ---------------------------- |
| `POST`   | `/v1/tasks/{id}/stopwatch/start`       | —                | `ClocksReply`                |
| `POST`   | `/v1/tasks/{id}/stopwatch/stop`        | —                | `ClocksReply`                |
| `POST`   | `/v1/tasks/{id}/stopwatch/reset`       | —                | `ClocksReply`                |
| `PUT`    | `/v1/tasks/{id}/timer`                 | `{length_ms}`    | `ClocksReply`                |
| `POST`   | `/v1/tasks/{id}/timer/pause`           | —                | `ClocksReply`                |
| `POST`   | `/v1/tasks/{id}/timer/resume`          | —                | `ClocksReply`                |
| `DELETE` | `/v1/tasks/{id}/timer`                 | —                | `ClocksReply`                |

- Every `Card` carries `stopwatch`, `timer` and `time_tracking`, each `null` while unused; `BoardDetail`,
  `TaskDetail` and `ClocksReply` carry `server_now`, the moment the server answered. A screen counts a running
  clock from `running_since` or `ends_at` against `server_now`, not against the device's clock alone (KT-D6).
- The stopwatch is the task's own clock (KT-D1): `total_ms` and `by_column` count closed spans, a running one adds
  `now − running_since`. Starting a running one or stopping a stopped one changes nothing; reset clears it.
- The timer counts down a length the person sets (KT-D3), 1 minute to 365 days: running while `ends_at` is set,
  paused while `paused_left_ms` is; below zero is the overrun. Pause or resume without a timer is `timer_not_set`.
- Plan and fact are `plan_minutes` and `fact_minutes` in `PATCH /v1/tasks/{id}` (0 to 6 000 000, `null` clears).
- The stopwatch's automations (KT-D2; default off, on, on) act while the board shows the stopwatch: start when a
  task arrives on the board (created, landed as incoming, a recurring task's next one); on a move, close the span
  in the old column, then stop for good when the task is done and `stop_on_done`, or start in the new column when
  it ran or `restart_on_move`; stop when the task is marked done and `stop_on_done`.
- A Jira task has none of the three (`jira_unsupported`).

## Development

`npm run dev` serves these routes from the mocks. The demo boards are Work (custom fields, covers, subtasks,
comments, attachments, a recurring task, tasks from a meeting with Leo's marks, a running stopwatch, a timer
running and one past zero, plan and fact), Home (recurring chores, a range)
and Romashka. Two generated boards of 300 and 1 000 cards appear after
`sessionStorage.setItem("kanban-demo-large", "1")` and a reload, for the performance measures.
