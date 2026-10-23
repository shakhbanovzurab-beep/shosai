import { apiClient } from "@/lib/api/app-client";
import { dataOf } from "@/lib/api/client";

import type {
  BoardSticker,
  BoardStickerPatch,
  CustomSticker,
  PlaceSticker,
  StickerPatch,
  StickersResponse,
} from "../domain/stickers-contract";

/* Поля на `/v1/stickers*` и `/v1/boards/{id}/stickers*` (TK-D12, план tasks §3.8). */

const sticker = (id: string) => ({ params: { path: { sticker_id: id } } });
const board = (boardId: string) => ({ params: { path: { board_id: boardId } } });
const onBoard = (boardId: string, stickerId: string) => ({
  params: { path: { board_id: boardId, sticker_id: stickerId } },
});

export const stickersApi = {
  /** Свои поля человека: доски, где они стоят, и сколько задач несут их значения. */
  list: (): Promise<StickersResponse> => dataOf(apiClient.GET("/v1/stickers")),
  patch: (id: string, body: StickerPatch): Promise<CustomSticker> =>
    dataOf(apiClient.PATCH("/v1/stickers/{sticker_id}", { ...sticker(id), body })),
  remove: (id: string): Promise<void> => dataOf(apiClient.DELETE("/v1/stickers/{sticker_id}", sticker(id))),
  place: (boardId: string, body: PlaceSticker): Promise<BoardSticker> =>
    dataOf(apiClient.POST("/v1/boards/{board_id}/stickers", { ...board(boardId), body })),
  patchOnBoard: (boardId: string, stickerId: string, body: BoardStickerPatch): Promise<BoardSticker> =>
    dataOf(apiClient.PATCH("/v1/boards/{board_id}/stickers/{sticker_id}", { ...onBoard(boardId, stickerId), body })),
  takeOff: (boardId: string, stickerId: string): Promise<void> =>
    dataOf(apiClient.DELETE("/v1/boards/{board_id}/stickers/{sticker_id}", onBoard(boardId, stickerId))),
};
