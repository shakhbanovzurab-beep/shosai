import { apiRequest, jsonBody } from "@/lib/api/request";

import type {
  BoardSticker,
  BoardStickerPatch,
  CustomSticker,
  PlaceSticker,
  StickerPatch,
  StickersResponse,
} from "../domain/stickers-contract";

/* Поля на `/v1/stickers*` и `/v1/boards/{id}/stickers*` (TK-D12, план tasks §3.8). */

const sticker = (id: string) => `/v1/stickers/${encodeURIComponent(id)}`;
const onBoard = (boardId: string, stickerId = "") =>
  `/v1/boards/${encodeURIComponent(boardId)}/stickers${stickerId ? `/${encodeURIComponent(stickerId)}` : ""}`;

export const stickersApi = {
  /** Свои поля человека: доски, где они стоят, и сколько задач несут их значения. */
  list: () => apiRequest<StickersResponse>("/v1/stickers"),
  patch: (id: string, body: StickerPatch) => apiRequest<CustomSticker>(sticker(id), jsonBody("PATCH", body)),
  remove: (id: string) => apiRequest<void>(sticker(id), { method: "DELETE" }),
  place: (boardId: string, body: PlaceSticker) => apiRequest<BoardSticker>(onBoard(boardId), jsonBody("POST", body)),
  show: (boardId: string, stickerId: string, body: BoardStickerPatch) =>
    apiRequest<BoardSticker>(onBoard(boardId, stickerId), jsonBody("PATCH", body)),
  takeOff: (boardId: string, stickerId: string) => apiRequest<void>(onBoard(boardId, stickerId), { method: "DELETE" }),
};
