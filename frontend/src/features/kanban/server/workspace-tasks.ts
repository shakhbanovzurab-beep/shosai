import { type MyTask, myTasks, updateMyTask } from "@/features/workspace/server";

import { taskOwners } from "../data/task-owners";
import type { ColumnKind, Task } from "../domain/board";
import type { StoredBoard } from "./demo-store";

/*
 * The user's workspace tasks on the board they picked. The board keeps only where each card sits and
 * its personal priority; everything else is read from the workspace task every time, and a move
 * between columns changes the task's status in the workspace.
 */

const cardId = (task: Pick<MyTask, "id" | "workspace">) => `ws:${task.workspace.id}:${task.id}`;

const KIND_BY_STATUS: Record<MyTask["status"], ColumnKind> = { todo: "todo", in_progress: "in_progress", done: "done" };
const STATUS_BY_KIND: Record<ColumnKind, MyTask["status"]> = { todo: "todo", in_progress: "in_progress", done: "done" };

/** The card of a workspace task; the screen words where it came from ("From …") in the user's language. */
function card(task: MyTask, existing?: Task): Task {
  return {
    id: cardId(task),
    title: task.title,
    description: "",
    priority: existing?.priority ?? "Medium",
    dueDate: task.due_on,
    progress: null,
    owner: taskOwners.arham,
    label: task.workspace.name,
    insights: [],
    workspace: {
      workspace_id: task.workspace.id,
      workspace_name: task.workspace.name,
      task_id: task.id,
      url: `/app/w/${encodeURIComponent(task.workspace.slug)}/tasks`,
      source: task.project_name ?? task.meeting_title,
    },
  };
}

/**
 * Brings the board in line with the user's workspace tasks: updates cards, moves a card whose status
 * changed in the workspace, adds new open assignments on top, drops tasks that are no longer theirs.
 * A board that isn't the chosen one loses its workspace cards. Bumps the revision only on change.
 */
export function reconcileWorkspaceTasks(stored: StoredBoard, isTarget: boolean) {
  const mine =
    isTarget && !stored.board.jira ? new Map(myTasks().map((t) => [cardId(t), t])) : new Map<string, MyTask>();
  const before = JSON.stringify(stored.tasks);
  const kindOf = new Map(stored.columns.map((c) => [c.id, c.kind]));
  const firstOf = (kind: ColumnKind) => stored.columns.find((c) => c.kind === kind)?.id;
  const placed = new Set<string>();
  const moving: { task: MyTask; existing: Task }[] = [];

  const next = Object.fromEntries(
    Object.entries(stored.tasks).map(([columnId, list]) => [
      columnId,
      list.flatMap((t) => {
        if (!t.workspace) return [t];
        const task = mine.get(t.id);
        if (!task) return [];
        placed.add(t.id);
        if (kindOf.get(columnId) !== KIND_BY_STATUS[task.status]) {
          moving.push({ task, existing: t });
          return [];
        }
        return [card(task, t)];
      }),
    ]),
  );
  for (const { task, existing } of moving) {
    const column = firstOf(KIND_BY_STATUS[task.status]);
    if (column) next[column] = [card(task, existing), ...(next[column] ?? [])];
  }
  for (const task of mine.values()) {
    const column = firstOf(KIND_BY_STATUS[task.status]);
    if (placed.has(cardId(task)) || task.status === "done" || !column) continue;
    next[column] = [card(task), ...(next[column] ?? [])];
  }
  stored.tasks = next;
  if (JSON.stringify(next) !== before) stored.revision++;
}

/** After a card moved or was renamed on the board: the same change to the workspace task. */
export function pushToWorkspace(
  stored: StoredBoard,
  task: Task,
  columnId: string | undefined,
  title: string | undefined,
) {
  if (!task.workspace) return;
  const kind = columnId ? stored.columns.find((c) => c.id === columnId)?.kind : undefined;
  const status = kind ? STATUS_BY_KIND[kind] : undefined;
  updateMyTask(task.workspace.workspace_id, task.workspace.task_id, { status, title });
}

export const isWorkspaceCard = (task: Task) => task.workspace !== undefined;
