import { redirect } from "react-router";

import { accountApi } from "@/features/workspace/api/workspace-api";
import { LAST_WORKSPACE_COOKIE, NEW_WORKSPACE_PATH, workspacePath } from "@/features/workspace/domain/paths";
import { readClientCookie } from "@/lib/cookie.client";

/** /app/w: последнее открытое пространство (или первое), а если их нет — страница «новое пространство». */
export async function loader() {
  const { workspaces } = await accountApi.workspaces();
  const last = readClientCookie(LAST_WORKSPACE_COOKIE) ?? "";
  const target = workspaces.find((workspace) => workspace.slug === last) ?? workspaces[0];
  return redirect(target ? workspacePath(target.slug) : NEW_WORKSPACE_PATH);
}

// Страница только перенаправляет: loader уходит до отрисовки.
export const Component = () => null;
