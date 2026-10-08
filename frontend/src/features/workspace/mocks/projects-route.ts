import { JsonResponse } from "@/mocks/runtime";

import type { WorkspaceState } from "../domain/contract";
import { canEditProject } from "../domain/roles";
import { stateOf } from "./demo-store";
import { type Ctx, type Found, type ItemCtx, inWorkspace, item } from "./guards";
import { type Problem, refuse } from "./problems";
import { firstIssue, projectInputSchema, readJson } from "./schemas";

const ok = ({ data, me }: Found, status = 200) => JsonResponse.json<WorkspaceState>(stateOf(data, me), { status });

/** Lead and team must belong to this workspace; null clears either. */
function checkRefs({ data }: Found, input: { lead_id?: string | null; team_id?: string | null }): Problem | null {
  if (input.lead_id && !data.members.some((m) => m.id === input.lead_id)) return "leadGone";
  if (input.team_id && !data.teams.some((t) => t.id === input.team_id)) return "teamGone";
  return null;
}

/** /api/workspaces/[ws]/projects: anyone can start a project; they lead it unless they pick someone else. */
export const projectsRoute = {
  POST: (request: Request, { params }: Ctx) =>
    inWorkspace(
      request,
      params,
      () => "/projects",
      async (found) => {
        const body = projectInputSchema.safeParse(await readJson(request));
        if (!body.success) return refuse(firstIssue(body.error), 422);
        const problem = checkRefs(found, body.data);
        if (problem) return refuse(problem, 422);
        found.data.projects.unshift({
          id: `p-${crypto.randomUUID().slice(0, 8)}`,
          ...body.data,
          lead_id: body.data.lead_id ?? found.me.id,
          created_at: new Date().toISOString(),
        });
        return ok(found, 201);
      },
    ),
};

/** /api/workspaces/[ws]/projects/[id]: its lead or an admin edits or deletes it. */
export const projectRoute = {
  PATCH: (request: Request, { params }: ItemCtx) =>
    inWorkspace(request, params, item("/projects"), async (found, { id }) => {
      const project = found.data.projects.find((p) => p.id === id);
      if (!project) return refuse("projectGone", 404);
      if (!canEditProject(found.me, project)) return refuse("projectEditDenied", 403);
      const body = projectInputSchema.partial().safeParse(await readJson(request));
      if (!body.success) return refuse(firstIssue(body.error), 422);
      const problem = checkRefs(found, body.data);
      if (problem) return refuse(problem, 422);
      Object.assign(project, body.data);
      return ok(found);
    }),

  /** Deleting a project keeps its meetings and tasks; they just stop belonging to it. */
  DELETE: (request: Request, { params }: ItemCtx) =>
    inWorkspace(request, params, item("/projects"), (found, { id }) => {
      const { data, me } = found;
      const project = data.projects.find((p) => p.id === id);
      if (!project) return refuse("projectGone", 404);
      if (!canEditProject(me, project)) return refuse("projectDeleteDenied", 403);
      data.projects = data.projects.filter((p) => p.id !== id);
      for (const m of data.meetings) if (m.project_id === id) m.project_id = null;
      for (const t of data.tasks) if (t.project_id === id) t.project_id = null;
      for (const k of data.knowledge) if (k.project_id === id) k.project_id = null;
      return ok(found);
    }),
};
