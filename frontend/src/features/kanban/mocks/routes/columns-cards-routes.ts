import type { ColumnHead } from "../../domain/boards-contract";
import { createCard, patchCard } from "../store/card-ops";
import { createColumn, deleteColumn, patchColumn } from "../store/column-ops";
import { cardOf } from "../store/present";
import type { StoredBoard, StoredColumn } from "../store/types";
import { cardCreateSchema, cardPatchSchema, columnCreateSchema, columnPatchSchema } from "./board-schemas";
import { bodyOf, type Params } from "./http";
import { answer, answerEmpty, withBoard } from "./respond";

/* `/v1/boards/{id}/columns*` и `/v1/boards/{id}/cards*` (план tasks §3.3, §3.8). */

const headOf = ({ card_ids: _cards, ...head }: StoredColumn): ColumnHead => head;
type ColumnParams = Params<"id" | "columnId">;
type CardParams = Params<"id" | "taskId">;
const sub = async (params: Promise<Record<string, string>>, key: string) => (await params)[key] ?? "";

/** /v1/boards/[id]/columns */
export const columnsRoute = {
  async POST(request: Request, { params }: Params<"id">) {
    return withBoard(params, async (board) => {
      const body = await bodyOf(request, columnCreateSchema);
      if ("refusal" in body) return body.refusal;
      return answer(createColumn(board, body.data), headOf, 201);
    });
  },
};

/** /v1/boards/[id]/columns/[columnId] */
export const columnRoute = {
  async PATCH(request: Request, { params }: ColumnParams) {
    return withBoard(params, async (board) => {
      const body = await bodyOf(request, columnPatchSchema);
      if ("refusal" in body) return body.refusal;
      return answer(patchColumn(board, await sub(params, "columnId"), body.data), headOf);
    });
  },
  async DELETE(_request: Request, { params }: ColumnParams) {
    return withBoard(params, async (board) => answerEmpty(deleteColumn(board, await sub(params, "columnId"))));
  },
};

const cardOn = (board: StoredBoard) => (task: Parameters<typeof cardOf>[0]) => cardOf(task, board);

/** /v1/boards/[id]/cards: новая задача на доске (на доске Jira — новая задача Jira) или копия. */
export const cardsRoute = {
  async POST(request: Request, { params }: Params<"id">) {
    return withBoard(params, async (board) => {
      const body = await bodyOf(request, cardCreateSchema);
      if ("refusal" in body) return body.refusal;
      return answer(createCard(board, body.data), cardOn(board), 201);
    });
  },
};

/** /v1/boards/[id]/cards/[taskId]: переименовать, приоритет, переместить; другой вид колонки — другой статус. */
export const cardRoute = {
  async PATCH(request: Request, { params }: CardParams) {
    return withBoard(params, async (board) => {
      const body = await bodyOf(request, cardPatchSchema);
      if ("refusal" in body) return body.refusal;
      return answer(patchCard(board, await sub(params, "taskId"), body.data), cardOn(board));
    });
  },
};
