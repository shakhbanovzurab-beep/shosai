import type { RouteObject } from "react-router";
import { describe, expect, it } from "vitest";

import { userPanelRoutes } from "./user-panel";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

/*
 * Leo открывает страницы кабинета только из списка сервера (`core.navigate`, отчёт владельца 2026-10-28: модель
 * выдумала /app/tasks). Список должен совпадать со страницами маршрутизатора, иначе Leo откроет «не найдено» или
 * не сможет открыть настоящую страницу.
 */

const PAGES_FILE = fileURLToPath(
  new URL("../../../../backend/src/shosai/features/agent/domain/cabinet_pages.py", import.meta.url),
);

const leoPages = () => [...readFileSync(PAGES_FILE, "utf8").matchAll(/^ {4}"(\/app[^"]*)":/gm)].map((m) => m[1]);

function pathOf(route: RouteObject, base: string): string {
  if (route.index) return base;
  return route.path?.startsWith("/") ? route.path : `${base}/${route.path ?? ""}`;
}

function routerPages(routes: RouteObject[], base: string): string[] {
  return routes.flatMap((route) => {
    const path = pathOf(route, base);
    const own = route.Component || route.lazy || route.element ? [path.replace(/\/$/, "")] : [];
    return [...(route.children ? [] : own), ...routerPages(route.children ?? [], path)];
  });
}

describe("the pages Leo may open", () => {
  it("are exactly the cabinet's pages", () => {
    const pages = new Set(routerPages(userPanelRoutes, ""));
    pages.delete("/app");

    expect(new Set(leoPages())).toEqual(pages);
  });
});
