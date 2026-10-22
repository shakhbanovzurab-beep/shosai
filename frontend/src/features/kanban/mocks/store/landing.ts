import { onArrival, onMove } from "./clock-ops";
import { advanceSync } from "./jira";
import { demo, firstColumnOf, placementOf } from "./state";
import type { StoredBoard, StoredTask } from "./types";
import { syncWorkspaceTasks } from "./workspace-bridge";

/*
 * Что сервер делает при чтении досок (план tasks §3.5, поток 2): карточка, чей статус разошёлся с видом
 * колонки, встаёт наверх первой колонки своего вида; на доску входящих приземляются открытые задачи, которые
 * пришли к человеку и ещё не лежат ни на одной его доске (TK-D4). Перестановки поднимают ревизию.
 */

function alignKinds(board: StoredBoard) {
  const tasks = demo().tasks;
  let moved = false;
  for (const column of board.columns)
    for (const id of [...column.card_ids]) {
      const task = tasks.get(id);
      if (!task || task.status === column.kind) continue;
      const target = firstColumnOf(board, task.status);
      if (!target) continue;
      column.card_ids.splice(column.card_ids.indexOf(id), 1);
      target.card_ids.unshift(id);
      onMove(board, id, column.id, target.id);
      moved = true;
    }
  if (moved) board.revision++;
}

/** Пришла к человеку: назначена ему в пространстве или из его встречи. */
const isIncoming = (task: StoredTask, mine: Set<string>) =>
  task.status !== "done" && (mine.has(task.id) || (task.space === null && task.source.kind === "meeting"));

function landIncoming(mine: Set<string>) {
  const d = demo();
  const board = d.incoming.board_id ? d.boards.get(d.incoming.board_id) : undefined;
  if (!board || board.jira) return;
  let landed = false;
  for (const task of d.tasks.values()) {
    if (!isIncoming(task, mine) || placementOf(task.id)) continue;
    const column = firstColumnOf(board, task.status);
    if (!column) continue;
    column.card_ids.unshift(task.id);
    onArrival(board, task.id, column.id);
    landed = true;
  }
  if (landed) board.revision++;
}

/** Открытых входящих задач, которые ждут доски, пока она не выбрана. */
export function openIncoming() {
  const mine = new Set(syncWorkspaceTasks().keys());
  return [...demo().tasks.values()].filter((task) => isIncoming(task, mine) && !placementOf(task.id)).length;
}

/** Всё, что меняется само к следующему чтению. */
export function reconcile() {
  const d = demo();
  for (const board of d.boards.values()) advanceSync(board);
  const mine = new Set(syncWorkspaceTasks().keys());
  for (const board of d.boards.values()) alignKinds(board);
  landIncoming(mine);
}
