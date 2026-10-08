import { JsonResponse } from "@/mocks/runtime";

import type { WorkspaceState } from "../domain/contract";
import { canManageMember, isAdmin } from "../domain/roles";
import { stateOf } from "./demo-store";
import { logEvent } from "./events";
import { type Ctx, type Found, type ItemCtx, inWorkspace, item } from "./guards";
import { refuse } from "./problems";
import { firstIssue, inviteSchema, readJson, updateMemberSchema } from "./schemas";
import { withdrawMember } from "./sharing";

const ok = ({ data, me }: Found, status = 200) => JsonResponse.json<WorkspaceState>(stateOf(data, me), { status });
const knownTeams = ({ data }: Found, ids: string[]) => ids.every((id) => data.teams.some((t) => t.id === id));

/** /api/workspaces/[ws]/invitations */
export const invitationsRoute = {
  POST: (request: Request, { params }: Ctx) =>
    inWorkspace(
      request,
      params,
      () => "/invitations",
      async (found) => {
        const { data, me } = found;
        if (!isAdmin(me) && !data.workspace.sharing.members_can_invite) return refuse("adminsInvitePeople", 403);
        const body = inviteSchema.safeParse(await readJson(request));
        if (!body.success) return refuse(firstIssue(body.error), 422);
        if (!knownTeams(found, body.data.team_ids)) return refuse("teamsGone", 422);
        if (body.data.role === "admin" && !isAdmin(me)) return refuse("adminsInviteAdmins", 403);
        const taken = new Set([...data.members, ...data.invitations].map((p) => p.email.toLowerCase()));
        const emails = [...new Set(body.data.emails.map((e) => e.toLowerCase()))].filter((e) => !taken.has(e));
        if (emails.length === 0) return refuse("allAlreadyInvited", 409);
        const left = Math.max(0, data.workspace.plan.seats - data.members.length - data.invitations.length);
        if (emails.length > left) return refuse((t) => t("seatsLeft", { count: left }), 409);
        const sent_at = new Date().toISOString();
        for (const email of emails)
          data.invitations.push({
            id: `inv-${crypto.randomUUID().slice(0, 8)}`,
            email,
            role: body.data.role,
            team_ids: body.data.team_ids,
            invited_by: me.id,
            sent_at,
          });
        logEvent(data, "member_invited", me, { target: emails.join(", ") });
        return ok(found, 201);
      },
    ),
};

/** /api/workspaces/[ws]/invitations/[id] */
export const invitationRoute = {
  DELETE: (request: Request, { params }: ItemCtx) =>
    inWorkspace(request, params, item("/invitations"), (found, { id }) => {
      const invitation = found.data.invitations.find((i) => i.id === id);
      if (!invitation) return refuse("invitationGone", 404);
      if (!isAdmin(found.me) && invitation.invited_by !== found.me.id) return refuse("adminsRevokeInvitation", 403);
      found.data.invitations = found.data.invitations.filter((i) => i.id !== id);
      logEvent(found.data, "invitation_revoked", found.me, { target: invitation.email });
      return ok(found);
    }),
};

/** /api/workspaces/[ws]/invitations/[id]/resend */
export const invitationResendRoute = {
  POST: (request: Request, { params }: ItemCtx) =>
    inWorkspace(
      request,
      params,
      (p) => `${item("/invitations")(p)}/resend`,
      (found, { id }) => {
        const invitation = found.data.invitations.find((i) => i.id === id);
        if (!invitation) return refuse("invitationGone", 404);
        invitation.sent_at = new Date().toISOString();
        return ok(found);
      },
    ),
};

/** /api/workspaces/[ws]/members/[id] */
export const memberRoute = {
  PATCH: (request: Request, { params }: ItemCtx) =>
    inWorkspace(request, params, item("/members"), async (found, { id }) => {
      const { data, me } = found;
      const target = data.members.find((m) => m.id === id);
      if (!target) return refuse("personGone", 404);
      const body = updateMemberSchema.safeParse(await readJson(request));
      if (!body.success) return refuse(firstIssue(body.error), 422);
      const { role, team_ids } = body.data;
      if (role !== undefined) {
        if (!canManageMember(me, target)) return refuse("roleChangeDenied", 403);
        if (target.role !== role) logEvent(data, "role_changed", me, { target: target.name, value: role });
        target.role = role;
      }
      if (team_ids !== undefined) {
        if (!knownTeams(found, team_ids)) return refuse("teamsGone", 422);
        const current = new Set(target.team_ids);
        const privateTeams = new Set(data.teams.filter((t) => t.private).map((t) => t.id));
        const joinsPrivate = team_ids.some((t) => !current.has(t) && privateTeams.has(t));
        if (!isAdmin(me) && (target.id !== me.id || joinsPrivate)) return refuse("adminsAddToTeam", 403);
        target.team_ids = team_ids;
      }
      return ok(found);
    }),

  /** Removes someone: what they own leaves with them, their open tasks wait for a new owner. */
  DELETE: (request: Request, { params }: ItemCtx) =>
    inWorkspace(request, params, item("/members"), (found, { id }) => {
      if (!isAdmin(found.me)) return refuse("adminsRemovePeople", 403);
      const target = found.data.members.find((m) => m.id === id);
      if (!target) return refuse("personGone", 404);
      if (!canManageMember(found.me, target)) return refuse("ownerCantBeRemoved", 403);
      withdrawMember(found.data, target);
      logEvent(found.data, "member_removed", found.me, { target: target.name });
      return ok(found);
    }),
};
