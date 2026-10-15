import { apiClient } from "@/lib/api/app-client";
import { dataOf } from "@/lib/api/client";
import type { components } from "@/lib/api/generated/schema";

import type { Me } from "../domain/session";

export type MePatch = components["schemas"]["MePatch"];

/** Изменить профиль или согласия; сервер возвращает сохранённого человека целиком. */
export function patchMe(change: MePatch): Promise<Me> {
  return dataOf(apiClient.PATCH("/v1/me", { body: change }));
}

/** Поставить аватар: тело запроса — само изображение, уже уменьшенное браузером. */
export function putAvatar(image: Blob): Promise<Me> {
  return dataOf(
    apiClient.PUT("/v1/me/avatar", {
      body: image as never,
      bodySerializer: (body: unknown) => body as Blob,
      headers: { "content-type": image.type },
    }),
  );
}

/** Убрать аватар: кабинет покажет инициалы. */
export function deleteAvatar(): Promise<Me> {
  return dataOf(apiClient.DELETE("/v1/me/avatar"));
}
