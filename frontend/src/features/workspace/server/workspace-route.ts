import { NextResponse } from "next/server";

import { forwardToBackend } from "@/server/backend-proxy";

import type { UsageResponse } from "../domain/content-contract";
import type { WorkspaceState, WorkspacesResponse } from "../domain/contract";
import { isAdmin } from "../domain/roles";
import { createWorkspace, deleteWorkspace, meIn, myWorkspaces, stateOf, summaryOf } from "./demo-store";
import { logEvent } from "./events";
import { type Ctx, inWorkspace } from "./guards";
import { refuse } from "./problems";
import { createWorkspaceSchema, firstIssue, readJson, updateWorkspaceSchema } from "./schemas";
import { withdrawMember } from "./sharing";

/** /api/workspaces: the workspaces the account is in, and a new one. */
export const workspacesRoute = {
  async GET(request: Request) {
    const upstream = await forwardToBackend(request, "/v1/workspaces");
    if (upstream) return upstream;
    const workspaces = myWorkspaces().flatMap((data) => {
      const me = meIn(data);
      return me ? [summaryOf(data, me)] : [];
    });
    return NextResponse.json<WorkspacesResponse>({ workspaces });
  },

  async POST(request: Request) {
    const upstream = await forwardToBackend(request, "/v1/workspaces");
    if (upstream) return upstream;
    const body = createWorkspaceSchema.safeParse(await readJson(request));
    if (!body.success) return refuse(firstIssue(body.error), 422);
    const { data, me } = createWorkspace(body.data.name, body.data.seats);
    return NextResponse.json<WorkspaceState>(stateOf(data, me), { status: 201 });
  },
};

/** /api/workspaces/[ws] */
export const workspaceRoute = {
  GET: (request: Request, { params }: Ctx) =>
    inWorkspace(
      request,
      params,
      () => "",
      ({ data, me }) => NextResponse.json<WorkspaceState>(stateOf(data, me)),
    ),

  PATCH: (request: Request, { params }: Ctx) =>
    inWorkspace(
      request,
      params,
      () => "",
      async ({ data, me }) => {
        if (!isAdmin(me)) return refuse("adminsChangeSettings", 403);
        const body = updateWorkspaceSchema.safeParse(await readJson(request));
        if (!body.success) return refuse(firstIssue(body.error), 422);
        const { name, join_domain, sharing } = body.data;
        if (name !== undefined) data.workspace.name = name;
        if (join_domain !== undefined) data.workspace.join_domain = join_domain;
        if (sharing) {
          data.workspace.sharing = { ...data.workspace.sharing, ...sharing };
          data.workspace.sharing_reviewed = true;
        }
        const changed = Object.keys(body.data).join(", ");
        if (changed) logEvent(data, "settings_changed", me, { value: changed });
        return NextResponse.json<WorkspaceState>(stateOf(data, me));
      },
    ),

  DELETE: (request: Request, { params }: Ctx) =>
    inWorkspace(
      request,
      params,
      () => "",
      ({ data, me }) => {
        if (me.role !== "owner") return refuse("ownerOnlyDelete", 403);
        deleteWorkspace(data.workspace.id);
        return new Response(null, { status: 204 });
      },
    ),
};

/** /api/workspaces/[ws]/leave: anyone but the owner; their recordings and documents leave with them. */
export const leaveRoute = {
  POST: (request: Request, { params }: Ctx) =>
    inWorkspace(
      request,
      params,
      () => "/leave",
      ({ data, me }) => {
        if (me.role === "owner") return refuse("ownerCantLeave", 409);
        withdrawMember(data, me);
        logEvent(data, "member_left", me);
        return new Response(null, { status: 204 });
      },
    ),
};

/** /api/workspaces/[ws]/usage: meetings and minutes per member this month, for admins. */
export const usageRoute = {
  GET: (request: Request, { params }: Ctx) =>
    inWorkspace(
      request,
      params,
      () => "/usage",
      ({ data, me }) => {
        if (!isAdmin(me)) return refuse("adminsSeeUsage", 403);
        const now = new Date();
        return NextResponse.json<UsageResponse>({
          month_start: new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1)).toISOString(),
          members: data.members.map(({ id }) => {
            const [meetings, minutes] = data.usage[id] ?? [0, 0];
            return { member_id: id, meetings, minutes };
          }),
        });
      },
    ),
};
