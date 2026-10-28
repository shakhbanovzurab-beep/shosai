import { MOCK_API } from "@/config/unserved-slices";
import { ApiError } from "@/lib/api/errors";

/*
 * «Новая трансляция»: название и зал ожидания. На моках — студия демо-трансляции; маршрут сервера появится в A12b,
 * а до тех пор пункт меню скрыт там, где моков нет (`broadcasts` в `config/unserved-slices.ts`).
 */

/** Создать трансляцию и вернуть путь её студии в кабинете. */
export async function createBroadcast(title: string, waitingRoom: boolean): Promise<string> {
  if (!MOCK_API) throw new ApiError("video_unavailable", 503, "video_unavailable");
  // На моках у студии постоянная ссылка; название и зал ожидания демо берёт из своего сценария.
  void title;
  void waitingRoom;
  return "/app/live/studio";
}
