import { apiClient } from "@/lib/api/app-client";
import { dataOf } from "@/lib/api/client";
import type { components } from "@/lib/api/generated/schema";

import type { BoardScene } from "../domain/board";

/* Маршруты доски по пропуску комнаты (MR-D13): сцена с версией и ссылка для картинки в хранилище владельца. */

type PictureLink = components["schemas"]["MeetingBoardPictureOut"];

export type SavedBoard = BoardScene & { version: number };

const params = (roomId: string, roomPass: string) => ({
  path: { room_id: roomId },
  header: { "X-Room-Pass": roomPass },
});

// Длину тела браузер ставит сам: заголовок из ссылки ему не передаётся.
const uploadHeaders = (headers: Record<string, string>) =>
  Object.fromEntries(Object.entries(headers).filter(([name]) => name.toLowerCase() !== "content-length"));

export const boardApi = {
  /** Сцена комнаты; версия 0 — доску ещё не сохраняли. */
  scene: async (roomId: string, roomPass: string): Promise<SavedBoard> => {
    const board = await dataOf(
      apiClient.GET("/v1/meetings/rooms/{room_id}/board", { params: params(roomId, roomPass) }),
    );
    return { elements: board.elements, files: board.files, version: board.version };
  },
  /** Сохранить сцену, сделанную на версии `version`; ответ — новая версия. */
  save: async (roomId: string, roomPass: string, scene: BoardScene, version: number): Promise<number> => {
    const body = { elements: [...scene.elements], files: { ...scene.files }, version };
    const saved = await dataOf(
      apiClient.PUT("/v1/meetings/rooms/{room_id}/board", { params: params(roomId, roomPass), body }),
    );
    return saved.version;
  },
  /** Положить PNG доски в хранилище владельца: ссылка на точный размер, затем сам файл прямо в бакет. */
  upload: async (roomId: string, roomPass: string, picture: Blob): Promise<void> => {
    const link: PictureLink = await dataOf(
      apiClient.POST("/v1/meetings/rooms/{room_id}/board/picture", {
        params: params(roomId, roomPass),
        body: { size_bytes: picture.size },
      }),
    );
    const stored = await fetch(link.url, { method: link.method, headers: uploadHeaders(link.headers), body: picture });
    if (!stored.ok) throw new Error(`the board's picture was not stored: HTTP ${stored.status}`);
  },
};
