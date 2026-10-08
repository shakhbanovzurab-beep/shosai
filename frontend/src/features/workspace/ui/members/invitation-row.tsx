"use client";

import { Mail, RotateCw, X } from "lucide-react";
import { useTranslations } from "use-intl";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

import type { Invitation, Member } from "../../domain/contract";
import { resendInvitation, revokeInvitation } from "../../model/people-actions";
import { useWorkspaceDates } from "../shared/use-dates";

/** A pending invitation: who, as what, sent by whom and when; resend or revoke it. */
export function InvitationRow({
  ws,
  invitation,
  me,
  members,
  canManage,
  now,
}: {
  ws: string;
  invitation: Invitation;
  me: Member;
  members: Member[];
  canManage: boolean;
  now: number;
}) {
  const t = useTranslations("workspaceMembers");
  const shared = useTranslations("workspace");
  const dates = useWorkspaceDates();
  const inviter = members.find((m) => m.id === invitation.invited_by);
  const ago = dates.ago(invitation.sent_at, now);
  let invitedBy = t("invitation.byFormerMember", { ago });
  if (inviter)
    invitedBy = inviter.id === me.id ? t("invitation.byYou", { ago }) : t("invitation.by", { name: inviter.name, ago });
  const mine = canManage || invitation.invited_by === me.id;
  return (
    <li className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
      <div className="flex min-w-0 flex-1 basis-60 items-center gap-3">
        <span className="grid size-8 shrink-0 place-items-center rounded-full border border-dashed">
          <Mail className="size-4 text-muted-foreground" aria-hidden="true" />
        </span>
        <div className="flex min-w-0 flex-col">
          <span dir="auto" className="truncate font-medium text-sm">
            {invitation.email}
          </span>
          <span className="truncate text-muted-foreground text-xs">{invitedBy}</span>
        </div>
      </div>
      <div className="ms-auto flex items-center gap-1">
        <Badge variant="outline" className="me-1 font-normal">
          {shared(`roles.${invitation.role}.label`)}
        </Badge>
        {mine ? (
          <>
            <Button variant="ghost" size="sm" onClick={() => void resendInvitation(ws, invitation, t)}>
              <RotateCw data-icon="inline-start" />
              {t("invitation.resend")}
            </Button>
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label={t("invitation.revokeFor", { email: invitation.email })}
              title={t("invitation.revoke")}
              onClick={() => void revokeInvitation(ws, invitation, t)}
            >
              <X />
            </Button>
          </>
        ) : null}
      </div>
    </li>
  );
}
