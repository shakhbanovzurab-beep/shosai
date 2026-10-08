import { JsonResponse } from "@/mocks/runtime";

import type { Task, TasksResponse } from "../domain/content-contract";
import { type Ctx, type Found, type ItemCtx, inWorkspace, item } from "./guards";
import { type Problem, refuse } from "./problems";
import { listTasks, taskFor, toTask } from "./projection";
import { firstIssue, readJson, taskCreateSchema, taskUpdateSchema } from "./schemas";

/** Assignee and project must belong to this workspace; null clears either. */
function checkRefs(
  { data }: Found,
  input: { assignee_id?: string | null; project_id?: string | null },
): Problem | null {
  if (input.assignee_id && !data.members.some((m) => m.id === input.assignee_id)) return "personGone";
  if (input.project_id && !data.projects.some((p) => p.id === input.project_id)) return "projectGone";
  return null;
}

/** /api/workspaces/[ws]/tasks: everything the member can see, and a new task (anyone can add one). */
export const tasksRoute = {
  GET: (request: Request, { params }: Ctx) =>
    inWorkspace(
      request,
      params,
      () => "/tasks",
      ({ data, me }) => JsonResponse.json<TasksResponse>({ tasks: listTasks(data, me) }),
    ),

  POST: (request: Request, { params }: Ctx) =>
    inWorkspace(
      request,
      params,
      () => "/tasks",
      async (found) => {
        const body = taskCreateSchema.safeParse(await readJson(request));
        if (!body.success) return refuse(firstIssue(body.error), 422);
        const problem = checkRefs(found, body.data);
        if (problem) return refuse(problem, 422);
        const task = {
          id: `t-${crypto.randomUUID().slice(0, 8)}`,
          ...body.data,
          status: "todo" as const,
          meeting_id: null,
          created_at: new Date().toISOString(),
        };
        found.data.tasks.unshift(task);
        return JsonResponse.json<Task>(toTask(found.data, found.me, task), { status: 201 });
      },
    ),
};

/** /api/workspaces/[ws]/tasks/[id]: anyone who can see a task can tick it off, reassign or reschedule it. */
export const taskRoute = {
  PATCH: (request: Request, { params }: ItemCtx) =>
    inWorkspace(request, params, item("/tasks"), async (found, { id }) => {
      const stored = taskFor(found.data, found.me, id);
      if (!stored) return refuse("taskNotFound", 404);
      const body = taskUpdateSchema.safeParse(await readJson(request));
      if (!body.success) return refuse(firstIssue(body.error), 422);
      const problem = checkRefs(found, body.data);
      if (problem) return refuse(problem, 422);
      Object.assign(stored, body.data);
      return JsonResponse.json<Task>(toTask(found.data, found.me, stored));
    }),
};
