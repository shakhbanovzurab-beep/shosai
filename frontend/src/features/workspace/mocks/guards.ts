import { membership } from "./demo-store";
import { refuse } from "./problems";
import type { StoredMember, WorkspaceData } from "./types";

export type Found = { data: WorkspaceData; me: StoredMember };

type WorkspaceParams = { ws: string };

/**
 * The common start of every workspace route: forward to the backend when there is one, otherwise
 * find the workspace and the account's member in it (404 for both "missing" and "not a member",
 * 423 while the platform's team has it suspended).
 */
export async function inWorkspace<P extends WorkspaceParams>(
  _request: Request,
  params: Promise<P>,
  _path: (p: P) => string,
  run: (found: Found, p: P) => Response | Promise<Response>,
): Promise<Response> {
  const p = await params;
  const found = membership(p.ws);
  if (!found) return refuse("notMember", 404);
  // The platform's team paused the workspace: nothing in it opens until they restore it.
  return found.data.control.suspended ? refuse("suspended", 423) : run(found, p);
}

export type Ctx = { params: Promise<{ ws: string }> };
export type ItemCtx = { params: Promise<{ ws: string; id: string }> };

export const item = (base: string) => (p: { id: string }) => `${base}/${encodeURIComponent(p.id)}`;
