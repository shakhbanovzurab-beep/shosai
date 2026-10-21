import { BOARD_COLUMNS_MAX, type ColumnCreate, type ColumnPatch } from "../../domain/boards-contract";
import { jiraRefusal } from "./jira";
import { fail, type Outcome, ok } from "./outcome";
import { touch } from "./state";
import type { StoredBoard, StoredColumn } from "./types";

/* Колонки (TK-D12): создать, изменить, удалить так, чтобы карточки не потерялись (KG-D9). */

const clamp = (value: number, max: number) => Math.max(0, Math.min(value, max));

export function createColumn(board: StoredBoard, request: ColumnCreate): Outcome<StoredColumn> {
  const refusal = jiraRefusal(board, true);
  if (refusal) return fail(refusal);
  if (board.columns.length >= BOARD_COLUMNS_MAX) return fail("board_columns_full");
  const column: StoredColumn = {
    id: crypto.randomUUID(),
    title: request.title,
    kind: request.kind,
    color: request.color ?? null,
    collapsed: false,
    card_ids: [],
  };
  board.columns.splice(clamp(request.position, board.columns.length), 0, column);
  touch(board);
  return ok(column);
}

/** На доске Jira — только цвет и сворачивание: это вид, в Jira он не уходит. */
export function patchColumn(board: StoredBoard, columnId: string, patch: ColumnPatch): Outcome<StoredColumn> {
  const column = board.columns.find((c) => c.id === columnId);
  if (!column) return fail("column_not_found");
  if (board.jira && (patch.title !== undefined || patch.position !== undefined)) return fail("managed_in_jira");
  if (patch.title !== undefined) column.title = patch.title;
  if (patch.color !== undefined) column.color = patch.color;
  if (patch.collapsed !== undefined) column.collapsed = patch.collapsed;
  if (patch.position !== undefined) {
    board.columns.splice(board.columns.indexOf(column), 1);
    board.columns.splice(clamp(patch.position, board.columns.length), 0, column);
  }
  touch(board);
  return ok(column);
}

/** Карточки удалённой колонки — наверх первой другой колонки того же вида, в своём порядке. */
export function deleteColumn(board: StoredBoard, columnId: string): Outcome<null> {
  const refusal = jiraRefusal(board, true);
  if (refusal) return fail(refusal);
  const column = board.columns.find((c) => c.id === columnId);
  if (!column) return fail("column_not_found");
  const heir = board.columns.find((c) => c.id !== columnId && c.kind === column.kind);
  if (!heir) return fail("last_column_of_kind");
  heir.card_ids.unshift(...column.card_ids);
  board.columns = board.columns.filter((c) => c.id !== columnId);
  touch(board);
  return ok(null);
}
