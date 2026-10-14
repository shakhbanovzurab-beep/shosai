import type { RouteObject } from "react-router";

import { signedInGuard } from "./guards";
import { page, pageWithData } from "./lazy-page";

const signedOutLoader = () => import("../pages/standalone/signed-out-loader");

/** Страницы кабинета вне обеих панелей; граница отдаёт их из кабинета (ADR 0021 §3, F2-D5). */
export const standaloneRoutes: RouteObject[] = [
  {
    // Общий каркас входа (своим чанком): афиша не перезапускается при переходе между этими страницами.
    ...page(() => import("../layouts/auth")),
    children: [
      {
        path: "/app/login",
        ...pageWithData(
          () => import("../pages/standalone/login-loader"),
          () => import("../pages/standalone/login"),
        ),
      },
      { path: "/app/register", ...pageWithData(signedOutLoader, () => import("../pages/standalone/register")) },
      { path: "/app/forgot", ...pageWithData(signedOutLoader, () => import("../pages/standalone/forgot")) },
      { path: "/app/reset", ...page(() => import("../pages/standalone/reset")) },
      {
        path: "/app/connect",
        loader: signedInGuard,
        ...page(() => import("../pages/standalone/connect")),
      },
    ],
  },
  { path: "/oauth/callback", ...page(() => import("../pages/standalone/oauth-callback")) },
  { path: "/unauthorized", ...page(() => import("../pages/standalone/unauthorized")) },
];
