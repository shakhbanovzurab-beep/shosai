import { MOCK_API } from "@/config/unserved-slices";

import { broadcastApi } from "../api/broadcast-api";

/* «Новая трансляция»: название и зал ожидания; на моках разработки — студия демо-трансляции. */

/** Путь трансляции в кабинете по её ссылке: `https://…/live/{token}` → `/app/live/{token}`. */
export const broadcastPathOf = (link: string) => `/app/live/${new URL(link).pathname.split("/").at(-1) ?? ""}`;

/** Создать трансляцию и вернуть путь её студии; повтор с тем же ключом — та же трансляция. */
export async function createBroadcast(title: string, waitingRoom: boolean, idempotencyKey: string): Promise<string> {
  if (MOCK_API) return "/app/live/studio";
  const made = await broadcastApi.create(title, waitingRoom, idempotencyKey);
  return broadcastPathOf(made.link);
}
