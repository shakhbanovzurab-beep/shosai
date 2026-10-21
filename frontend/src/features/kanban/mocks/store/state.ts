import { largeBoardsOn, seedLargeBoards } from "../seed/large-boards";
import { seedPersonalBoards } from "../seed/personal-boards";
import { seedWorkBoard } from "../seed/work-board";
import type { KanbanDemo, StoredBoard, StoredColumn, StoredTask } from "./types";

/*
 * Хранилище моков досок и задач в памяти вкладки; сбрасывается перезагрузкой. Одно на страницу, поэтому живёт
 * на globalThis, как хранилища других слайсов.
 */

function seeded(): KanbanDemo {
  const demo: KanbanDemo = {
    tasks: new Map(),
    boards: new Map(),
    stickers: new Map(),
    values: new Map(),
    subtasks: new Map(),
    comments: new Map(),
    attachments: new Map(),
    incoming: { board_id: null },
  };
  seedWorkBoard(demo);
  seedPersonalBoards(demo);
  if (largeBoardsOn()) seedLargeBoards(demo);
  return demo;
}

const shared = globalThis as typeof globalThis & { kanbanTasksDemo?: KanbanDemo };

export function demo(): KanbanDemo {
  shared.kanbanTasksDemo ??= seeded();
  return shared.kanbanTasksDemo;
}

/** Начать с чистых демо-данных — для тестов. */
export function resetDemo() {
  shared.kanbanTasksDemo = seeded();
  return shared.kanbanTasksDemo;
}

export const now = () => new Date().toISOString();

/** Изменение доски: ревизия растёт с каждым. */
export function touch(board: StoredBoard) {
  board.revision++;
  if (board.jira?.sync_status === "synced") board.jira = { ...board.jira, last_synced_at: now() };
}

export type Placement = { board: StoredBoard; column: StoredColumn; index: number };

/** Где лежит задача на досках человека: у задачи не больше одного места (план tasks §3.4). */
export function placementOf(taskId: string): Placement | null {
  for (const board of demo().boards.values())
    for (const column of board.columns) {
      const index = column.card_ids.indexOf(taskId);
      if (index >= 0) return { board, column, index };
    }
  return null;
}

/** Убрать задачу с её места; доска, с которой она ушла, или null. */
export function unplace(taskId: string): StoredBoard | null {
  const at = placementOf(taskId);
  if (!at) return null;
  at.column.card_ids.splice(at.index, 1);
  return at.board;
}

/** Изменилось то, что видно на карточке: ревизия доски, где лежит задача. */
export function touchTask(taskId: string) {
  const at = placementOf(taskId);
  if (at) touch(at.board);
}

export const firstColumnOf = (board: StoredBoard, kind: StoredColumn["kind"]) =>
  board.columns.find((column) => column.kind === kind) ?? null;

export const findTask = (id: string): StoredTask | null => demo().tasks.get(id) ?? null;
export const findBoard = (id: string): StoredBoard | null => demo().boards.get(id) ?? null;
