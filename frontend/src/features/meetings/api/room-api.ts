import { apiClient } from "@/lib/api/app-client";
import { dataOf } from "@/lib/api/client";
import type { components } from "@/lib/api/generated/schema";

import type { WebDevice } from "../domain/web-device";

/** Что сервер даёт сессии звонка при входе (`POST /v1/meetings/join/{token}`). */
export type JoinedRoom = components["schemas"]["JoinOut"];
export type OwnedRoom = components["schemas"]["RoomOut"];

export const roomApi = {
  /** Вход по ссылке: гость называет себя, вошедший человек входит под именем профиля. */
  join: (token: string, name: string | null, device: WebDevice): Promise<JoinedRoom> =>
    dataOf(
      apiClient.POST("/v1/meetings/join/{token}", {
        params: { path: { token } },
        body: { ...(name === null ? {} : { name }), device },
      }),
    ),
  /** «Новая встреча» сейчас: комната в Личном пространстве, один раз на ключ. */
  open: (idempotencyKey: string): Promise<OwnedRoom> =>
    dataOf(
      apiClient.POST("/v1/meetings/rooms", { params: { header: { "Idempotency-Key": idempotencyKey } }, body: {} }),
    ),
};
