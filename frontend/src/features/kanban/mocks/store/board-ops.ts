import { BOARD_TEMPLATES, type BoardIcon, type BoardTemplate, type TemplateColumn } from "../../domain/board";
import { BOARDS_MAX, type Layout } from "../../domain/boards-contract";
import { NEW_BOARD_SYSTEM_VISIBILITY } from "../../domain/stickers-contract";
import { DEFAULT_STOPWATCH_AUTOMATIONS } from "../../domain/time-contract";
import { jiraRefusal } from "./jira";
import { fail, type Outcome, ok } from "./outcome";
import { isShown } from "./present";
import { demo, now, touch } from "./state";
import type { StoredBoard } from "./types";

function isShownId(id: string) {
  const task = demo().tasks.get(id);
  return task !== undefined && isShown(task);
}

/* Доски: создание по шаблону, раскладка, удаление (TK-D6), доска входящих (TK-D4). */

/** Новая доска; колонки шаблона названы на языке запроса (`columnName`). */
export function createBoard(
  name: string,
  icon: BoardIcon,
  template: BoardTemplate,
  columnName: (column: TemplateColumn) => string,
): Outcome<StoredBoard> {
  const d = demo();
  if (d.boards.size >= BOARDS_MAX) return fail("boards_full");
  const board: StoredBoard = {
    id: crypto.randomUUID(),
    name,
    icon,
    created_at: now(),
    jira: null,
    syncUntil: null,
    revision: 1,
    columns: BOARD_TEMPLATES[template].map((c) => ({
      id: crypto.randomUUID(),
      title: columnName(c.name),
      kind: c.kind,
      color: null,
      collapsed: false,
      card_ids: [],
    })),
    system: { ...NEW_BOARD_SYSTEM_VISIBILITY },
    stopwatch: { ...DEFAULT_STOPWATCH_AUTOMATIONS },
    stickers: [],
  };
  d.boards.set(board.id, board);
  return ok(board);
}

/**
 * Удалить доску (TK-D6): её места уходят; задачи, сделанные на ней руками, удаляются; задачи встреч и
 * пространств остаются без доски; у доски Jira уходят её отражённые задачи, в самой Jira ничего не удаляется.
 */
export function deleteBoard(board: StoredBoard) {
  const d = demo();
  for (const id of board.columns.flatMap((c) => c.card_ids)) {
    const task = d.tasks.get(id);
    if (task && task.space === null && (task.source.kind === "manual" || task.source.kind === "jira")) {
      d.tasks.delete(id);
      for (const map of [d.values, d.subtasks, d.comments, d.attachments]) map.delete(id);
    }
  }
  d.boards.delete(board.id);
  if (d.incoming.board_id === board.id) d.incoming.board_id = null;
}

export function setIncoming(boardId: string | null): Outcome<null> {
  const d = demo();
  if (boardId !== null) {
    const board = d.boards.get(boardId);
    if (!board) return fail("board_not_found");
    if (board.jira) return fail("jira_not_incoming");
  }
  d.incoming.board_id = boardId;
  return ok(null);
}

/** Вся раскладка разом: колонки и карточки должны быть те же, только в другом порядке. */
export function applyLayout(board: StoredBoard, layout: Layout): Outcome<null> {
  const refusal = jiraRefusal(board, true);
  if (refusal) return fail(refusal);
  const byId = new Map(board.columns.map((c) => [c.id, c]));
  if (layout.columns.length !== byId.size || layout.columns.some((c) => !byId.has(c.id))) return fail("board_changed");
  // Сверяются только карточки, которые доска показывает: закрытые больше 30 дней назад клиент не видит (TK-D5).
  const shown = (ids: string[]) => ids.filter((id) => isShownId(id));
  for (const column of layout.columns) {
    const current = shown(byId.get(column.id)?.card_ids ?? [])
      .toSorted()
      .join();
    if (current !== column.task_ids.toSorted().join()) return fail("board_changed");
  }
  board.columns = layout.columns.flatMap((c) => {
    const column = byId.get(c.id);
    const hidden = (column?.card_ids ?? []).filter((id) => !isShownId(id));
    return column ? [{ ...column, title: c.title, card_ids: [...c.task_ids, ...hidden] }] : [];
  });
  touch(board);
  return ok(null);
}
