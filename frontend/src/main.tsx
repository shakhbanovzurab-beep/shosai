import "./app/globals.css";

import { StrictMode } from "react";

import { createRoot } from "react-dom/client";
import { type RouteObject, RouterProvider } from "react-router";

import { createRouter } from "./app/router";
import { reloadOnStaleChunk } from "./app/stale-chunk-reload";
import { startTagManagerWhenIdle } from "./features/consent/model/consent-store";

// Моки API включаются только в `npm run dev` (F2-D1); в production-сборке этой ветки нет.
async function mockRoutes(): Promise<RouteObject[]> {
  if (!import.meta.env.DEV || import.meta.env.MODE === "api") return [];
  const { startMockApi } = await import("./mocks/browser");
  return startMockApi();
}

async function start() {
  reloadOnStaleChunk();
  const root = document.getElementById("root");
  if (!root) throw new Error("index.html has no #root");
  const router = createRouter(await mockRoutes());
  createRoot(root).render(
    <StrictMode>
      <RouterProvider router={router} />
    </StrictMode>,
  );
  // GTM — после первого кадра, на простое браузера; без контейнера в сборке не делает ничего (ADR 0047).
  startTagManagerWhenIdle();
}

void start();
