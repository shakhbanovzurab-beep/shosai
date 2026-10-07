import type { BoardState, Task, TaskOwnerProfile, TaskPriority } from "./board";

const PRIORITY_RANK: Record<TaskPriority, number> = { High: 0, Medium: 1, Low: 2 };

export type TaskLocation = { columnId: string; index: number; task: Task };

export function locateTask(board: BoardState, taskId: string): TaskLocation | null {
  for (const [columnId, tasks] of Object.entries(board)) {
    const index = tasks.findIndex((task) => task.id === taskId);
    if (index >= 0) return { columnId, index, task: tasks[index] };
  }
  return null;
}

function insertAt<T>(list: T[], index: number, item: T) {
  return [...list.slice(0, index), item, ...list.slice(index)];
}

export const withoutTask = (board: BoardState, taskId: string): BoardState => {
  const at = locateTask(board, taskId);
  if (!at) return board;
  return { ...board, [at.columnId]: board[at.columnId].filter((task) => task.id !== taskId) };
};

export const insertTask = (board: BoardState, columnId: string, index: number, task: Task): BoardState => ({
  ...board,
  [columnId]: insertAt(board[columnId] ?? [], index, task),
});

/** Moves a task to `index` in a column, which may be the one it is already in. */
export function placeTask(board: BoardState, taskId: string, columnId: string, index: number): BoardState {
  const at = locateTask(board, taskId);
  if (!at) return board;
  const rest = withoutTask(board, taskId);
  return insertTask(rest, columnId, Math.min(index, (rest[columnId] ?? []).length), at.task);
}

/** Moves a task to the top or bottom of a column. */
export function moveTask(board: BoardState, taskId: string, columnId: string, edge: "top" | "bottom"): BoardState {
  const length = (withoutTask(board, taskId)[columnId] ?? []).length;
  return placeTask(board, taskId, columnId, edge === "top" ? 0 : length);
}

export function updateTask(board: BoardState, taskId: string, patch: Partial<Task>): BoardState {
  const at = locateTask(board, taskId);
  if (!at) return board;
  return {
    ...board,
    [at.columnId]: board[at.columnId].map((task) => (task.id === taskId ? { ...task, ...patch } : task)),
  };
}

/** Stable sort, so tasks of equal priority keep their order. */
export const sortByPriority = (board: BoardState, columnId: string): BoardState => ({
  ...board,
  [columnId]: (board[columnId] ?? []).toSorted((a, b) => PRIORITY_RANK[a.priority] - PRIORITY_RANK[b.priority]),
});

export const newTask = (id: string, title: string, owner: TaskOwnerProfile | null): Task => ({
  id,
  title,
  description: "",
  priority: "Medium",
  dueDate: null,
  progress: null,
  owner,
  label: null,
  insights: [],
});

/** A copy of a task under a new id; the caller names it ("Plan (copy)" in the user's language). */
export const duplicateOf = (task: Task, id: string, title: string): Task => {
  const { jira: _issue, ...rest } = task;
  return { ...rest, id, title };
};

/**
 * Swaps a column with the one before it (-1) or after it (1) in the board's order, which reads from the
 * start of the line: left to right, or right to left in Arabic. At either end the order stays as it is.
 */
export function shiftColumn(order: string[], columnId: string, by: -1 | 1): string[] {
  const from = order.indexOf(columnId);
  const to = from + by;
  if (from < 0 || to < 0 || to >= order.length) return order;
  const next = [...order];
  [next[from], next[to]] = [next[to], next[from]];
  return next;
}
