import { NextResponse } from "next/server";

import { forwardToBackend } from "@/server/backend-proxy";

import type { Task } from "../domain/board";
import { locateTask } from "../domain/board-rules";
import type { TaskPatch } from "../domain/contract";
import { createTask, deleteTasks, patchTask } from "./board-ops";
import { editProblem, getBoard } from "./demo-store";
import { refuse } from "./problems";
import { firstIssue, readJson, taskCreateSchema, taskPatchSchema, tasksDeleteSchema } from "./schemas";

type BoardParams = { params: Promise<{ id: string }> };
type TaskParams = { params: Promise<{ id: string; taskId: string }> };
const path = (id: string, rest: string) => `/v1/kanban/boards/${encodeURIComponent(id)}${rest}`;

/** The board, or the response to send instead: not found, or a change this board doesn't allow now. */
function editable(id: string, appOnly: boolean) {
  const stored = getBoard(id);
  if (!stored) return { error: refuse("boardNotFound", 404) } as const;
  const problem = editProblem(stored, appOnly);
  return problem ? ({ error: refuse(problem.problem, problem.status) } as const) : ({ stored } as const);
}

/** /api/kanban/boards/[id]/tasks: a new task, or on a Jira board a new issue. Copies are app-only. */
export const tasksRoute = {
  async POST(request: Request, { params }: BoardParams) {
    const { id } = await params;
    const upstream = await forwardToBackend(request, path(id, "/tasks"));
    if (upstream) return upstream;
    const body = taskCreateSchema.safeParse(await readJson(request));
    if (!body.success) return refuse(firstIssue(body.error), 422);
    const board = editable(id, body.data.copy_of !== undefined);
    if ("error" in board) return board.error;
    const result = createTask(board.stored, body.data);
    return result.ok ? NextResponse.json<Task>(result.value, { status: 201 }) : refuse(result.problem, result.status);
  },
};

/** /api/kanban/boards/[id]/tasks/[taskId]: rename, reprioritize or move; on Jira, the issue changes too. */
export const taskRoute = {
  async PATCH(request: Request, { params }: TaskParams) {
    const { id, taskId } = await params;
    const upstream = await forwardToBackend(request, path(id, `/tasks/${encodeURIComponent(taskId)}`));
    if (upstream) return upstream;
    const body = taskPatchSchema.safeParse(await readJson(request));
    if (!body.success) return refuse(firstIssue(body.error), 422);
    const board = editable(id, false);
    if ("error" in board) return board.error;
    const result = patchTask(board.stored, taskId, body.data as TaskPatch);
    return result.ok ? NextResponse.json<Task>(result.value) : refuse(result.problem, result.status);
  },
};

/** /api/kanban/boards/[id]/tasks/delete: app boards only; Jira issues are deleted in Jira. */
export const tasksDeleteRoute = {
  async POST(request: Request, { params }: BoardParams) {
    const { id } = await params;
    const upstream = await forwardToBackend(request, path(id, "/tasks/delete"));
    if (upstream) return upstream;
    const body = tasksDeleteSchema.safeParse(await readJson(request));
    if (!body.success) return refuse(firstIssue(body.error), 422);
    const board = editable(id, true);
    if ("error" in board) return board.error;
    const linked = body.data.task_ids.some((taskId) => locateTask(board.stored.tasks, taskId)?.task.workspace);
    if (linked) return refuse("workspaceTaskDelete", 409);
    deleteTasks(board.stored, body.data.task_ids);
    return new Response(null, { status: 204 });
  },
};
