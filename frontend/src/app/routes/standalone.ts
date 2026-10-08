import type { RouteObject } from "react-router";

import { page } from "./lazy-page";

/** Страницы кабинета вне обеих панелей; граница отдаёт их из кабинета (ADR 0021 §3, F2-D5). */
export const standaloneRoutes: RouteObject[] = [
  { path: "/oauth/callback", ...page(() => import("../pages/standalone/oauth-callback")) },
  { path: "/unauthorized", ...page(() => import("../pages/standalone/unauthorized")) },
];
