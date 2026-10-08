"use client";

import { toast } from "sonner";

import { apiErrorDescription } from "@/lib/api/error-description";
import { errorMessage } from "@/lib/errors";

import type { AssignableRole, Invitation, InviteRequest, Member, WorkspaceState } from "../domain/contract";
import { refreshAccount, refreshShared, resourcesOf } from "./resources";
import type { MembersWords } from "./words";
import { applyState } from "./workspace-actions";

async function run(call: () => Promise<WorkspaceState>, success: string, failure: string) {
  try {
    applyState(await call());
    toast.success(success);
    return true;
  } catch (error) {
    toast.error(failure, { description: apiErrorDescription(error) });
    return false;
  }
}

/** Sends the invitations; resolves to null on success or the message to show in the dialog. */
export async function invitePeople(ws: string, request: InviteRequest, t: MembersWords): Promise<string | null> {
  try {
    applyState(await resourcesOf(ws).api.invite(request));
    toast.success(t("toasts.invitationsSent", { count: request.emails.length, email: request.emails[0] ?? "" }));
    return null;
  } catch (error) {
    return errorMessage(error) ?? t("toasts.inviteFailed");
  }
}

export const revokeInvitation = (ws: string, invitation: Invitation, t: MembersWords) =>
  run(
    () => resourcesOf(ws).api.revokeInvitation(invitation.id),
    t("toasts.invitationRevoked", { email: invitation.email }),
    t("toasts.revokeFailed"),
  );

export const resendInvitation = (ws: string, invitation: Invitation, t: MembersWords) =>
  run(
    () => resourcesOf(ws).api.resendInvitation(invitation.id),
    t("toasts.invitationResent", { email: invitation.email }),
    t("toasts.resendFailed"),
  );

export const changeRole = (ws: string, member: Member, role: AssignableRole, t: MembersWords) =>
  run(
    () => resourcesOf(ws).api.updateMember(member.id, { role }),
    t("toasts.roleChanged", { name: member.name, role }),
    t("toasts.roleChangeFailed"),
  );

export const setMemberTeams = (ws: string, member: Member, teamIds: string[], message: string, t: MembersWords) =>
  run(() => resourcesOf(ws).api.updateMember(member.id, { team_ids: teamIds }), message, t("toasts.teamsUpdateFailed"));

export async function removeMember(ws: string, member: Member, t: MembersWords) {
  const removed = await run(
    () => resourcesOf(ws).api.removeMember(member.id),
    t("toasts.memberRemoved", { name: member.name }),
    t("toasts.removeMemberFailed"),
  );
  // What they owned left with them; their open tasks now wait for a new owner.
  if (removed) {
    refreshShared(ws);
    void resourcesOf(ws).knowledge.refresh();
    refreshAccount();
  }
  return removed;
}
