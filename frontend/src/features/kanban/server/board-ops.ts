import { JIRA_CATALOG, JIRA_SITE, NEW_ISSUE_TYPE } from "../data/jira-catalog";
import { taskOwners } from "../data/task-owners";
import { BOARD_TEMPLATES, type BoardIcon, type BoardTemplate, type Task, type TemplateColumn } from "../domain/board";
import { duplicateOf, insertTask, locateTask, newTask, placeTask, updateTask } from "../domain/board-rules";
import type { JiraBoard, LayoutUpdate, TaskCreate, TaskPatch } from "../domain/contract";
import { boards, jiraConnected, type StoredBoard, startSync, touch } from "./demo-store";
import type { Problem } from "./problems";
import { pushToWorkspace } from "./workspace-tasks";

/* The demo's board and task operations; route handlers check input and permissions before calling these. */

export type Outcome<T> = { ok: true; value: T } | { ok: false; status: number; problem: Problem };
const fail = (status: number, problem: Problem): Outcome<never> => ({ ok: false, status, problem });
function ok<T>(value: T): Outcome<T> {
  return { ok: true, value };
}

/** A new app board; its template's columns get the names `columnName` gives them, in the user's language. */
export function createAppBoard(
  name: string,
  icon: BoardIcon,
  template: BoardTemplate,
  columnName: (column: TemplateColumn) => string,
): StoredBoard {
  const id = crypto.randomUUID();
  const columns = BOARD_TEMPLATES[template].map((c) => ({
    id: crypto.randomUUID(),
    title: columnName(c.name),
    kind: c.kind,
  }));
  const stored: StoredBoard = {
    board: { id, name, icon, jira: null, created_at: new Date().toISOString() },
    columns,
    tasks: Object.fromEntries(columns.map((c) => [c.id, []])),
    revision: 1,
    syncUntil: null,
    syncProblem: null,
  };
  boards.set(id, stored);
  return stored;
}

const syncedWith = (boardId: number) =>
  [...boards.values()].find((b) => b.board.jira?.board_id === boardId)?.board.id ?? null;

export function jiraBoards(): JiraBoard[] {
  if (!jiraConnected()) return [];
  return JIRA_CATALOG.map(({ board_id, name, project_key, project_name, type }) => ({
    site: JIRA_SITE,
    board_id,
    name,
    project_key,
    project_name,
    type,
    synced_board_id: syncedWith(board_id),
  }));
}

export function connectJiraBoard(site: string, boardId: number): Outcome<StoredBoard> {
  if (!jiraConnected()) return fail(409, "connectJiraFirst");
  const source = JIRA_CATALOG.find((b) => b.board_id === boardId);
  if (site !== JIRA_SITE || !source) return fail(404, "jiraBoardUnavailable");
  if (syncedWith(boardId)) return fail(409, "jiraBoardSynced");
  const id = crypto.randomUUID();
  const stored: StoredBoard = {
    board: {
      id,
      name: source.name,
      icon: "rocket",
      jira: {
        site,
        project_key: source.project_key,
        board_id: boardId,
        board_name: source.name,
        board_url: `https://${site}/jira/software/projects/${source.project_key}/boards/${boardId}`,
        sync_status: "syncing",
        sync_error: null,
        last_synced_at: null,
      },
      created_at: new Date().toISOString(),
    },
    columns: source.columns,
    tasks: {},
    revision: 1,
    syncUntil: null,
    syncProblem: null,
  };
  boards.set(id, stored);
  startSync(stored);
  return ok(stored);
}

/** Applies an app board's layout; the columns and tasks must be the board's own, only reordered. */
export function applyLayout(stored: StoredBoard, layout: LayoutUpdate): Outcome<null> {
  const known = new Set(stored.columns.map((c) => c.id));
  if (layout.columns.length !== known.size || layout.columns.some((c) => !known.has(c.id)))
    return fail(409, "boardChanged");
  for (const column of layout.columns) {
    const current = (stored.tasks[column.id] ?? []).map((t) => t.id).toSorted();
    if (current.join() !== column.task_ids.toSorted().join()) return fail(409, "boardChanged");
  }
  const byId = new Map(stored.columns.map((c) => [c.id, c]));
  stored.columns = layout.columns.flatMap((c) => {
    const column = byId.get(c.id);
    return column ? [{ ...column, title: c.title }] : [];
  });
  stored.tasks = Object.fromEntries(
    layout.columns.map((c) => {
      const tasks = new Map((stored.tasks[c.id] ?? []).map((t) => [t.id, t]));
      return [c.id, c.task_ids.flatMap((id) => tasks.get(id) ?? [])];
    }),
  );
  touch(stored);
  return ok(null);
}

/** On a Jira board the new task is a new issue in the project, with the next key. */
function jiraIssueFor(stored: StoredBoard, task: Task): Task {
  const link = stored.board.jira;
  if (!link) return task;
  const numbers = Object.values(stored.tasks)
    .flat()
    .map((t) => Number(t.jira?.key.split("-")[1] ?? 0));
  const key = `${link.project_key}-${Math.max(0, ...numbers) + 1}`;
  return {
    ...task,
    id: `jira-${key}`,
    label: NEW_ISSUE_TYPE,
    jira: { key, url: `https://${link.site}/browse/${key}`, type: NEW_ISSUE_TYPE },
  };
}

/** A new task, or a copy of `copy_of` named with the request's title (the client words "(copy)"). */
export function createTask(stored: StoredBoard, request: TaskCreate): Outcome<Task> {
  if (!stored.columns.some((c) => c.id === request.column_id)) return fail(404, "columnNotFound");
  let task = newTask(crypto.randomUUID(), request.title, taskOwners.arham);
  if (request.copy_of) {
    const source = locateTask(stored.tasks, request.copy_of);
    if (!source) return fail(404, "taskNotFound");
    if (source.task.workspace) return fail(409, "workspaceTaskCopy");
    task = duplicateOf(source.task, task.id, request.title);
  }
  task = jiraIssueFor(stored, task);
  stored.tasks = insertTask(stored.tasks, request.column_id, request.position, task);
  touch(stored);
  return ok(task);
}

export function patchTask(stored: StoredBoard, taskId: string, patch: TaskPatch): Outcome<Task> {
  const at = locateTask(stored.tasks, taskId);
  if (!at) return fail(404, "taskNotFound");
  const { column_id, position, ...fields } = patch;
  let next = updateTask(stored.tasks, taskId, fields);
  if (column_id !== undefined) {
    if (!stored.columns.some((c) => c.id === column_id)) return fail(404, "columnNotFound");
    next = placeTask(next, taskId, column_id, position ?? 0);
  }
  stored.tasks = next;
  touch(stored);
  // A workspace task's card: the move or the new title is the workspace task's.
  pushToWorkspace(stored, at.task, column_id, fields.title);
  return ok(locateTask(next, taskId)?.task ?? at.task);
}

export function deleteTasks(stored: StoredBoard, ids: string[]) {
  const remove = new Set(ids);
  stored.tasks = Object.fromEntries(
    Object.entries(stored.tasks).map(([c, list]) => [c, list.filter((t) => !remove.has(t.id))]),
  );
  touch(stored);
}
