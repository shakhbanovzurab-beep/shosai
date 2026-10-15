import type { RouteObject } from "react-router";

import { adminLoginPathOf } from "@/features/admin-sign-in/domain/login-path";

import { adminPanelRoutes } from "./admin-panel";
import { adminSignInGuard, signedInGuard } from "./guards";
import { page, pageWithData } from "./lazy-page";

// Экраны админки (`/admin/<экран>`): адрес входа не может занять ни один из них.
const ADMIN_SCREENS = adminPanelRoutes.flatMap((route) => route.children ?? []).flatMap((child) => child.path ?? []);
const ADMIN_LOGIN_PATH = adminLoginPathOf(import.meta.env.VITE_ADMIN_LOGIN_PATH, ADMIN_SCREENS);

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
  // Вход в админку — по адресу из сборки (ADR 0049); без него маршрута нет.
  ...(ADMIN_LOGIN_PATH
    ? [
        {
          path: ADMIN_LOGIN_PATH,
          loader: adminSignInGuard,
          ...page(() => import("../pages/admin/sign-in")),
        },
      ]
    : []),
];
