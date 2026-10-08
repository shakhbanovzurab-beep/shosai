import type { RouteObject } from "react-router";

import { page, pageWithData } from "./lazy-page";
import { redirectRoute } from "./redirects";
import { workspaceRoutes } from "./workspace";

/** Пользовательская панель /app/*: отдельная почта, затем все страницы в рамке панели. */
export const userPanelRoutes: RouteObject[] = [
  {
    path: "/app/inbox",
    ...page(() => import("../layouts/inbox")),
    children: [{ index: true, ...page(() => import("../pages/user/inbox")) }],
  },
  {
    path: "/app",
    ...page(() => import("../layouts/user-panel")),
    children: [
      redirectRoute("", "/app/productivity"),
      { path: "productivity", ...page(() => import("../pages/user/productivity")) },
      { path: "calendar", ...page(() => import("../pages/user/calendar")) },
      {
        path: "download",
        ...pageWithData(
          () => import("../pages/user/download-loader"),
          () => import("../pages/user/download"),
        ),
      },
      {
        path: "file-manager",
        ...page(() => import("../layouts/file-manager")),
        children: [
          { index: true, ...page(() => import("../pages/user/file-manager")) },
          { path: "folders/:folderId", ...page(() => import("../pages/user/folder")) },
        ],
      },
      { path: "hub", ...page(() => import("../pages/user/hubs")) },
      { path: "hub/:hubId", ...page(() => import("../pages/user/hub")) },
      { path: "kanban", ...page(() => import("../pages/user/kanban")) },
      {
        path: "knowledge-base",
        ...page(() => import("../layouts/knowledge-base")),
        children: [{ index: true, ...page(() => import("../pages/user/knowledge-base")) }],
      },
      { path: "mail", ...page(() => import("../pages/user/mail")) },
      { path: "meetings", ...page(() => import("../pages/user/meetings")) },
      { path: "notes", ...page(() => import("../pages/user/notes")) },
      {
        path: "notes/:id",
        ...pageWithData(
          () => import("../pages/user/note-loader"),
          () => import("../pages/user/note"),
        ),
      },
      { path: "studio", ...page(() => import("../pages/user/studio")) },
      { path: "support", ...page(() => import("../pages/user/support")) },
      { path: "upgrade", ...page(() => import("../pages/user/upgrade")) },
      ...workspaceRoutes,
    ],
  },
];
