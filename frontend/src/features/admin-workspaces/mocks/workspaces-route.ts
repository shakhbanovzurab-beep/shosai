import { z } from "zod";

import {
  type ControlResult,
  platformWorkspace,
  platformWorkspaces,
  removeWorkspace,
  resumeWorkspace,
  setSeats,
  suspendWorkspace,
  transferOwnership,
} from "@/features/workspace/mocks/control";
import { detail, JsonResponse } from "@/mocks/runtime";

import {
  type AdminWorkspaceDetail,
  type AdminWorkspacesResponse,
  SEATS_LIMIT,
  SUSPEND_REASON_MAX,
} from "../domain/contract";
import { toDetail, toRow } from "./projection";

type Context = { params: Promise<{ id: string }> };

const GONE = "Пространство не найдено: возможно, его удалили.";

const seatsSchema = z.strictObject({ seats: z.int("Укажите целое число мест.").min(1).max(SEATS_LIMIT) });
const suspendSchema = z.strictObject({
  reason: z.string().trim().min(3, "Укажите причину: её увидят другие администраторы.").max(SUSPEND_REASON_MAX),
});
const ownerSchema = z.strictObject({ member_id: z.string().min(1).max(64) });

const readJson = (request: Request) => request.json().catch(() => null);
const firstIssue = (error: z.ZodError) => error.issues[0]?.message ?? "Проверьте данные.";

const answer = (result: ControlResult) =>
  result.ok ? JsonResponse.json<AdminWorkspaceDetail>(toDetail(result.data)) : detail(result.message, result.status);

/** `/api/admin/workspaces`: every workspace on the platform. */
export const workspacesRoute = {
  async GET(_request: Request) {
    return JsonResponse.json<AdminWorkspacesResponse>({ workspaces: platformWorkspaces().map(toRow) });
  },
};

/** `/api/admin/workspaces/{id}`: one workspace, its seats, and deleting it. */
export const workspaceRoute = {
  async GET(_request: Request, { params }: Context) {
    const { id } = await params;
    const data = platformWorkspace(id);
    return data ? JsonResponse.json<AdminWorkspaceDetail>(toDetail(data)) : detail(GONE, 404);
  },

  async PATCH(request: Request, { params }: Context) {
    const { id } = await params;
    const body = seatsSchema.safeParse(await readJson(request));
    if (!body.success) return detail(firstIssue(body.error), 422);
    return answer(setSeats(id, body.data.seats));
  },

  async DELETE(_request: Request, { params }: Context) {
    const { id } = await params;
    return removeWorkspace(id) ? new Response(null, { status: 204 }) : detail(GONE, 404);
  },
};

/** `/api/admin/workspaces/{id}/suspend`: pauses access for everyone in it, with the reason. */
export const suspendRoute = {
  async POST(request: Request, { params }: Context) {
    const { id } = await params;
    const body = suspendSchema.safeParse(await readJson(request));
    if (!body.success) return detail(firstIssue(body.error), 422);
    return answer(suspendWorkspace(id, body.data.reason));
  },
};

/** `/api/admin/workspaces/{id}/resume`: restores access. */
export const resumeRoute = {
  async POST(_request: Request, { params }: Context) {
    const { id } = await params;
    return answer(resumeWorkspace(id));
  },
};

/** `/api/admin/workspaces/{id}/owner`: hands ownership to another member. */
export const ownerRoute = {
  async POST(request: Request, { params }: Context) {
    const { id } = await params;
    const body = ownerSchema.safeParse(await readJson(request));
    if (!body.success) return detail(firstIssue(body.error), 422);
    return answer(transferOwnership(id, body.data.member_id));
  },
};
