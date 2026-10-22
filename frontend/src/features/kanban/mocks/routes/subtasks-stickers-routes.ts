import type { StickersResponse } from "../../domain/stickers-contract";
import { reconcile } from "../store/landing";
import { stickersOf } from "../store/present";
import {
  deleteSticker,
  ownedStickers,
  patchBoardSticker,
  patchSticker,
  placeSticker,
  removeSticker,
} from "../store/sticker-ops";
import { createSubtask, deleteSubtask, patchSubtask } from "../store/thread-ops";
import { bodyOf, json, type Params } from "./http";
import { answer, answerEmpty, withBoard, withTask } from "./respond";
import {
  boardStickerPatchSchema,
  placeStickerSchema,
  stickerPatchSchema,
  subtaskCreateSchema,
  subtaskPatchSchema,
} from "./task-schemas";

/* `/v1/tasks/{id}/subtasks*`, `/v1/stickers*` и `/v1/boards/{id}/stickers*` (план tasks §3.8). */

const sub = async (params: Promise<Record<string, string>>, key: string) => (await params)[key] ?? "";
const same = <T>(value: T) => value;

/** /v1/tasks/[id]/subtasks */
export const subtasksRoute = {
  async POST(request: Request, { params }: Params<"id">) {
    return withTask(params, async (task) => {
      const body = await bodyOf(request, subtaskCreateSchema);
      if ("refusal" in body) return body.refusal;
      return answer(createSubtask(task, body.data), same, 201);
    });
  },
};

/** /v1/tasks/[id]/subtasks/[subtaskId] */
export const subtaskRoute = {
  async PATCH(request: Request, { params }: Params<"id" | "subtaskId">) {
    return withTask(params, async (task) => {
      const body = await bodyOf(request, subtaskPatchSchema);
      if ("refusal" in body) return body.refusal;
      return answer(patchSubtask(task, await sub(params, "subtaskId"), body.data), same);
    });
  },
  async DELETE(_request: Request, { params }: Params<"id" | "subtaskId">) {
    return withTask(params, async (task) => answerEmpty(deleteSubtask(task, await sub(params, "subtaskId"))));
  },
};

/** /v1/stickers: свои поля человека — для «Поля других досок». */
export const stickersRoute = {
  async GET() {
    reconcile();
    return json<StickersResponse>({ items: ownedStickers() });
  },
};

/** /v1/stickers/[id] */
export const stickerRoute = {
  async PATCH(request: Request, { params }: Params<"id">) {
    const body = await bodyOf(request, stickerPatchSchema);
    if ("refusal" in body) return body.refusal;
    return answer(patchSticker(await sub(params, "id"), body.data), same);
  },
  async DELETE(_request: Request, { params }: Params<"id">) {
    return answerEmpty(deleteSticker(await sub(params, "id")));
  },
};

/** /v1/boards/[id]/stickers: поставить своё поле или новое. */
export const boardStickersRoute = {
  async POST(request: Request, { params }: Params<"id">) {
    return withBoard(params, async (board) => {
      const body = await bodyOf(request, placeStickerSchema);
      if ("refusal" in body) return body.refusal;
      return answer(placeSticker(board, body.data), same, 201);
    });
  },
};

/** /v1/boards/[id]/stickers/[stickerId]: показать на карточках или снять с доски. */
export const boardStickerRoute = {
  async PATCH(request: Request, { params }: Params<"id" | "stickerId">) {
    return withBoard(params, async (board) => {
      const body = await bodyOf(request, boardStickerPatchSchema);
      if ("refusal" in body) return body.refusal;
      const id = await sub(params, "stickerId");
      const shown = patchBoardSticker(board, id, body.data);
      return answer(shown, () => stickersOf(board).find((s) => s.id === id));
    });
  },
  async DELETE(_request: Request, { params }: Params<"id" | "stickerId">) {
    return withBoard(params, async (board) => answerEmpty(removeSticker(board, await sub(params, "stickerId"))));
  },
};
