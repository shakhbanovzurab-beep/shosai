import { createApiClient } from "./client";
import { type SessionPort, sessionMiddleware } from "./session-middleware";

/**
 * Единственный клиент API кабинета: через него слайсы ходят в `/v1`. Сессию к нему подключает точка сборки
 * приложения (main.tsx) один раз, до первого запроса, — так слайсам не нужно знать, как устроен вход.
 */
export const apiClient = createApiClient();

let attached = false;

/** Подключить сессию: bearer и обновление по 401. Повторный вызов ничего не меняет. */
export function attachSession(port: SessionPort): void {
  if (attached) return;
  apiClient.use(sessionMiddleware(port));
  attached = true;
}
