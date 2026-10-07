import type { BoardIcon, BoardSummary, BoardTemplate, TaskPriority } from "./board";

/**
 * Kanban API contract, shared by the Kanban screen and its route handlers in `../server` (served
 * under `/api/kanban`). They forward to `${BACKEND_API_URL}/v1/kanban/*` when it is set and
 * otherwise answer from an in-memory demo. snake_case to match Pydantic; errors are
 * `{ "detail": string }`. See docs/kanban-api.md.
 *
 * GET    /kanban/boards                           → BoardsResponse
 * POST   /kanban/boards                           → 201 BoardSummary     (CreateBoardRequest)
 * GET    /kanban/boards/{id}                      → BoardDetail
 * PATCH  /kanban/boards/{id}                      → BoardSummary         (BoardPatch)
 * DELETE /kanban/boards/{id}                      → 204; a Jira board stops syncing, nothing is deleted in Jira
 * PUT    /kanban/boards/{id}/layout               → 204                  (LayoutUpdate; app boards only)
 * POST   /kanban/boards/{id}/tasks                → 201 Task             (TaskCreate)
 * PATCH  /kanban/boards/{id}/tasks/{task_id}      → Task                 (TaskPatch)
 * POST   /kanban/boards/{id}/tasks/delete         → 204                  (TasksDelete; app boards only)
 * POST   /kanban/boards/{id}/sync                 → BoardSummary         (Jira boards: sync now)
 * PUT    /kanban/workspace-tasks                  → BoardsResponse       (WorkspaceTasksTarget: where your workspace tasks show)
 * GET    /kanban/jira/boards                      → JiraBoardsResponse   (boards the Jira connection can see)
 * POST   /kanban/jira/boards                      → 201 BoardSummary     (ConnectJiraBoardRequest; starts syncing)
 *
 * On a Jira board, columns are Jira's and every change goes to Jira: moving a task transitions the
 * issue to the column's first status, a new task creates an issue, title and priority update it.
 * Changes made in Jira arrive through Jira webhooks. Column layout, duplicates and deletes are
 * refused with 409 there (they're done in Jira).
 */

export type BoardsResponse = {
  boards: BoardSummary[];
  /** Where the user's workspace tasks show (null: nowhere yet), and how many open ones they have. */
  workspace_tasks: { board_id: string | null; open: number };
};

/**
 * The app board that shows the tasks assigned to you in your workspaces, or null for none. Those
 * cards follow the tasks: a new assignment appears, a finished or reassigned task moves or leaves.
 */
export type WorkspaceTasksTarget = { board_id: string | null };

export type CreateBoardRequest = { name: string; icon: BoardIcon; template: BoardTemplate };

export type BoardPatch = { name?: string; icon?: BoardIcon };

/** The whole layout of an app board: column order and titles, and the order of tasks in each. */
export type LayoutUpdate = { columns: { id: string; title: string; task_ids: string[] }[] };

/** A new task at `position` (0 = top) in a column, or a copy of `copy_of` placed there; either is named `title`. */
export type TaskCreate = { column_id: string; position: number; title: string; copy_of?: string };

/** Moving sends `column_id` and `position` together. */
export type TaskPatch = { title?: string; priority?: TaskPriority; column_id?: string; position?: number };

export type TasksDelete = { task_ids: string[] };

/** A board on a Jira site the user's Jira connection can read. */
export type JiraBoard = {
  site: string;
  board_id: number;
  name: string;
  project_key: string;
  project_name: string;
  type: "kanban" | "scrum";
  /** The app board already synced with it, if any. */
  synced_board_id: string | null;
};

/** `connected` is false until the user connects Jira in Settings › Connectors; boards are then empty. */
export type JiraBoardsResponse = { connected: boolean; account: string | null; boards: JiraBoard[] };

export type ConnectJiraBoardRequest = { site: string; board_id: number };
