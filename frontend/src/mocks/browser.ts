import { setupWorker } from "msw/browser";
import type { RouteObject } from "react-router";

import { mockRoutes } from "./handlers";
import { voiceSocket } from "./leo-voice-socket";
import { toHttpHandlers } from "./routing";

/** Страницы, существующие только с моками: заглушка экрана согласия OAuth провайдера. */
const mockPages: RouteObject[] = [{ path: "/oauth/demo-authorize", lazy: () => import("./demo-authorize-page") }];

/**
 * Отдаёт примерный API из браузера в `npm run dev` (F2-D1). Запросы, на которые моки не отвечают (ресурсы,
 * каталоги, сторонние сервисы), уходят в сеть как обычно. Возвращает страницы, которые добавляют моки.
 */
export async function startMockApi(): Promise<RouteObject[]> {
  // Голосовой режим Leo — сокет, а не HTTP: его мок перехватывает WebSocket страницы.
  const worker = setupWorker(...toHttpHandlers(mockRoutes), voiceSocket);
  await worker.start({
    serviceWorker: { url: "/mockServiceWorker.js", options: { scope: "/" } },
    onUnhandledFrame: "bypass",
    quiet: true,
  });
  return mockPages;
}
