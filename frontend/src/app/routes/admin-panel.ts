import type { RouteObject } from "react-router";

import { page } from "./lazy-page";
import { redirectRoute } from "./redirects";

/** Админ-панель /admin/*, только на русском. */
export const adminPanelRoutes: RouteObject[] = [
  {
    path: "/admin",
    ...page(() => import("../layouts/admin-panel")),
    children: [
      redirectRoute("", "/admin/dashboard"),
      { path: "dashboard", ...page(() => import("../pages/admin/dashboard")) },
      { path: "ai-models", ...page(() => import("../pages/admin/ai-models")) },
      { path: "apps", ...page(() => import("../pages/admin/apps")) },
      { path: "billing", ...page(() => import("../pages/admin/billing")) },
      { path: "errors", ...page(() => import("../pages/admin/errors")) },
      { path: "errors/:id", ...page(() => import("../pages/admin/issue")) },
      { path: "livekit", ...page(() => import("../pages/admin/livekit")) },
      { path: "plans", ...page(() => import("../pages/admin/plans")) },
      { path: "platform-prompts", ...page(() => import("../pages/admin/platform-prompts")) },
      { path: "profile", ...page(() => import("../pages/admin/profile")) },
      { path: "support", ...page(() => import("../pages/admin/support")) },
      { path: "users", ...page(() => import("../pages/admin/users")) },
      { path: "users/:id", ...page(() => import("../pages/admin/user")) },
      { path: "workspaces", ...page(() => import("../pages/admin/workspaces")) },
      { path: "workspaces/:id", ...page(() => import("../pages/admin/workspace")) },
    ],
  },
];
