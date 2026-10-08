import type { RouteObject } from "react-router";

import { page } from "./lazy-page";

/** Командные пространства /app/w/*: переход к последнему, создание и страницы одного пространства. */
export const workspaceRoutes: RouteObject[] = [
  { path: "w", ...page(() => import("../pages/workspace/workspaces-redirect")) },
  { path: "w/new", ...page(() => import("../pages/workspace/new")) },
  {
    path: "w/:workspace",
    ...page(() => import("../layouts/workspace")),
    children: [
      { index: true, ...page(() => import("../pages/workspace/home")) },
      { path: "decisions", ...page(() => import("../pages/workspace/decisions")) },
      { path: "knowledge", ...page(() => import("../pages/workspace/knowledge")) },
      { path: "meetings", ...page(() => import("../pages/workspace/meetings")) },
      { path: "meetings/:id", ...page(() => import("../pages/workspace/meeting")) },
      { path: "members", ...page(() => import("../pages/workspace/members")) },
      { path: "projects", ...page(() => import("../pages/workspace/projects")) },
      { path: "projects/:id", ...page(() => import("../pages/workspace/project")) },
      { path: "settings", ...page(() => import("../pages/workspace/settings")) },
      { path: "tasks", ...page(() => import("../pages/workspace/tasks")) },
    ],
  },
];
