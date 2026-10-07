/* Where the Workspace pages live: each workspace under its own slug, so links can be shared. */

export const WORKSPACES_ROOT = "/app/w";

/** Remembers the workspace opened last, so /app/w can open it again (read on the server). */
export const LAST_WORKSPACE_COOKIE = "last-workspace";

/** The page that starts a new workspace; "new" is never a workspace slug. */
export const NEW_WORKSPACE_PATH = `${WORKSPACES_ROOT}/new`;

/** `/app/w/lumen` + "/tasks" → "/app/w/lumen/tasks". */
export const workspacePath = (slug: string, path = "") => `${WORKSPACES_ROOT}/${encodeURIComponent(slug)}${path}`;

export const meetingPath = (slug: string, meetingId: string) =>
  workspacePath(slug, `/meetings/${encodeURIComponent(meetingId)}`);

export const projectPath = (slug: string, projectId: string) =>
  workspacePath(slug, `/projects/${encodeURIComponent(projectId)}`);

/** The workspace slug in a path, or null outside the Workspace pages (and on the "new" page). */
export function workspaceSlugFromPath(pathname: string): string | null {
  if (!pathname.startsWith(`${WORKSPACES_ROOT}/`)) return null;
  const slug = decodeURIComponent(pathname.slice(WORKSPACES_ROOT.length + 1).split("/")[0] ?? "");
  return slug && slug !== "new" ? slug : null;
}

/** True on any Workspace page, including the index and the "new" page. */
export const isWorkspacesPath = (pathname: string) =>
  pathname === WORKSPACES_ROOT || pathname.startsWith(`${WORKSPACES_ROOT}/`);
