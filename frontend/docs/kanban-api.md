# Kanban API

The contract between the Kanban screen (`/app/kanban`) and the FastAPI backend. The TypeScript types
in `src/features/kanban/domain/board.ts` and `domain/contract.ts` are the source of truth (snake_case).
The browser calls `/api/kanban/*`, which forwards to `${BACKEND_API_URL}/v1/kanban/*` when set and
otherwise answers from an in-memory demo (`src/features/kanban/server/`). Errors: `{"detail": "message"}`.

Words the API writes itself (error details, `sync_error`, the columns of a new board) are in the request's
interface language; the demo takes it from the `ui_language` cookie (see `docs/i18n.md`). Dates are data:
`Task.dueDate` is a calendar day (`"2026-06-26"`) or null, and the screen formats it.

| Method   | Path                                   | Body                                             | Response              |
| -------- | -------------------------------------- | ------------------------------------------------ | --------------------- |
| `GET`    | `/kanban/boards`                       | —                                                | `BoardsResponse`      |
| `POST`   | `/kanban/boards`                       | `{name, icon, template: "simple" \| "project"}`  | `201 BoardSummary`    |
| `GET`    | `/kanban/boards/{id}`                  | —                                                | `BoardDetail`         |
| `PATCH`  | `/kanban/boards/{id}`                  | `{name?, icon?}`                                 | `BoardSummary`        |
| `DELETE` | `/kanban/boards/{id}`                  | —                                                | `204`                 |
| `PUT`    | `/kanban/boards/{id}/layout`           | `{columns: [{id, title, task_ids}]}`             | `204` (app boards)    |
| `POST`   | `/kanban/boards/{id}/tasks`            | `{column_id, position, title, copy_of?}`         | `201 Task`            |
| `PATCH`  | `/kanban/boards/{id}/tasks/{task_id}`  | `{title?, priority?, column_id?, position?}`     | `Task`                |
| `POST`   | `/kanban/boards/{id}/tasks/delete`     | `{task_ids}`                                     | `204` (app boards)    |
| `POST`   | `/kanban/boards/{id}/sync`             | —                                                | `BoardSummary`        |
| `PUT`    | `/kanban/workspace-tasks`              | `{board_id: string \| null}`                     | `BoardsResponse`      |
| `GET`    | `/kanban/jira/boards`                  | —                                                | `JiraBoardsResponse`  |
| `POST`   | `/kanban/jira/boards`                  | `{site, board_id}`                               | `201 BoardSummary`    |

## Boards

A user has any number of boards ("Work", "Home"…), each with its own columns. A column has a `kind`
(`todo`, `in_progress`, `done`) that drives how cards look (progress while in progress, "Done" when
done) and maps to Jira's status categories. `BoardDetail.revision` goes up with every change, including
changes that arrive from Jira; the screen re-reads a board when it is opened again and, for Jira
boards, when the tab becomes visible.

- A new board's columns come from its template (`simple`: To do, In progress, Done; `project`: Backlog,
  To do, In progress, Review, Done), named in the request's language; after that they are the user's.
- `copy_of` copies a task under the request's `title`, which the screen words ("Plan (copy)").
- `layout` replaces column order, column titles and the order of tasks in each column at once; the
  columns and tasks must be the board's own (`409` if the board changed meanwhile).
- `position` is the index in the target column, `0` is the top. Moving sends `column_id` and
  `position` together.
- Deleting is a soft action in the UI: the screen hides the task and sends `tasks/delete` once its
  Undo toast closes.

## Workspace tasks on a board

Tasks assigned to the user in their workspaces (see `workspace-api.md`, `GET /me/tasks`) can show on
one app board of their choice. Nothing lands on a board until they pick one: `BoardsResponse.workspace_tasks`
is `{board_id, open}` (`board_id` null: nowhere yet; `open`: how many open tasks they have), and the
chosen board has `receives_workspace_tasks: true`. `PUT /kanban/workspace-tasks` picks a board or, with
`null`, takes the cards off; a Jira board is refused (`409`).

- A card is a view of the workspace task, not a copy: `Task.workspace` is
  `{workspace_id, workspace_name, task_id, url, source}` (`source`: the project or meeting it came from,
  or null) and the card's id is `ws:{workspace_id}:{task_id}`.
  The board stores only where the card sits and its personal `priority`; title, due date and source
  are read from the workspace task each time the board is read.
- Reading the board reconciles it: new open assignments go on top of the first column of the matching
  kind, a task whose status changed in the workspace moves to such a column, and tasks that are done
  before they ever showed, reassigned, deleted, or no longer visible to the user leave the board.
- Moving a card to a column of another `kind` sets the workspace task's status (`todo`,
  `in_progress`, `done`); renaming it renames the workspace task. Other columns of the same kind
  keep their own order.
- Refused with `409`: `copy_of` a workspace card, and `tasks/delete` with one in `task_ids` (they
  leave when they're done or reassigned in the workspace). Clearing a column keeps them.

## Jira boards (two-way sync)

Jira access comes from the Jira connector in Settings › Connectors (OAuth 2.0, Atlassian 3LO; see
`settings-api.md`). Scopes needed: `read:jira-work`, `write:jira-work`, `read:jira-user`,
`offline_access`; plus webhook registration.

- `GET /kanban/jira/boards` lists the boards on every site the connection can reach
  (`/oauth/token/accessible-resources`, then Jira Software `GET /rest/agile/1.0/board`). With no Jira
  connection it answers `{"connected": false, "account": null, "boards": []}`.
- `POST /kanban/jira/boards` creates a board with `jira` set and `sync_status: "syncing"`, then imports
  in the background: columns from `GET /rest/agile/1.0/board/{id}/configuration` (each column with its
  statuses; `kind` from the status category), issues from `GET /rest/agile/1.0/board/{id}/issue`. Task
  ids are stable per issue; `jira: {key, url, type}`; `label` is the issue type; `owner` the assignee.
  The board is read-only until `last_synced_at` is set.
- Changes made here go to Jira at once:
  - moving a task → `POST /rest/api/3/issue/{key}/transitions` to the first status of the target
    column, then rank (`PUT /rest/agile/1.0/issue/rank`) next to its neighbours;
  - a new task → `POST /rest/api/3/issue` in the board's project with the column's status;
  - `title` → `summary`, `priority` → the matching Jira priority (High, Medium, Low).
  If Jira refuses (no transition to that status, missing permission) answer `409` with Jira's reason;
  the screen puts the card back.
- Changes made in Jira come back through a registered webhook (`jira:issue_created`,
  `jira:issue_updated`, `jira:issue_deleted`, `board_configuration_changed`); each one updates the
  board and bumps `revision`. `POST /sync` pulls everything again on demand.
- Not available on Jira boards, `409`: `layout` (columns are configured in Jira), `copy_of`,
  `tasks/delete`. `DELETE /kanban/boards/{id}` only stops syncing and unregisters the webhook; nothing
  is deleted in Jira.
- If the Jira connection is removed or its token can't be refreshed: `sync_status: "error"` with
  `sync_error` saying so, and changes answer `409` until Jira is connected again.
