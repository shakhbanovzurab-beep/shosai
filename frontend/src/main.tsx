import "./app/globals.css";

import { StrictMode } from "react";

import { createRoot } from "react-dom/client";
import { type RouteObject, RouterProvider } from "react-router";

import { createRouter } from "./app/router";
import { reloadOnStaleChunk } from "./app/stale-chunk-reload";
import { startTagManagerWhenIdle } from "./features/consent/model/consent-store";
import { accessToken, renewSession, startSession } from "./features/identity/model/session";
import { attachSession } from "./lib/api/app-client";

// Моки API включаются только в `npm run dev` (F2-D1); в production-сборке этой ветки нет.
async function mockRoutes(): Promise<RouteObject[]> {
  if (!import.meta.env.DEV || import.meta.env.MODE === "api") return [];
  const { startMockApi } = await import("./mocks/browser");
  return startMockApi();
}

async function start() {
  reloadOnStaleChunk();
  attachSession({ accessToken, renew: renewSession });
  const root = document.getElementById("root");
  if (!root) throw new Error("index.html has no #root");
  const extraRoutes = await mockRoutes();
  // Сессия начинает обновляться до роутера: охрана панелей ждёт уже идущий запрос, а не начинает его. Её
  // отказ (сеть, 5xx) получает та же охрана и показывает страницу ошибки; здесь он только не всплывает дважды.
  startSession().catch(() => undefined);
  const router = createRouter(extraRoutes);
  createRoot(root).render(
    <StrictMode>
      <RouterProvider router={router} />
    </StrictMode>,
  );
  // GTM — после первого кадра, на простое браузера; без контейнера в сборке не делает ничего (ADR 0047).
  startTagManagerWhenIdle();
}

void start();
