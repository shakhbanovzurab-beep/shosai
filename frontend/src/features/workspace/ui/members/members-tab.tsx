"use client";

import { useState } from "react";

import { FilterX } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { useNow } from "@/hooks/use-now";

import { visibleTeams } from "../../domain/people";
import { useWorkspace } from "../../model/use-workspace";
import { EmptyMessage } from "../shared/empty-message";
import { SearchField } from "../shared/filters";
import { TeamSection } from "../shared/layout";
import { InvitationRow } from "./invitation-row";
import { MemberRow } from "./member-row";

const ROLE_ORDER = { owner: 0, admin: 1, member: 2 } as const;

/** Pending invitations first (they need a nudge or a revoke), then everyone, owner and admins on top. */
export function MembersTab() {
  const t = useTranslations("workspaceMembers");
  const { ws, state, can } = useWorkspace();
  const now = useNow();
  const [q, setQ] = useState("");
  const words = q.trim().toLowerCase();
  const match = (...fields: (string | null)[]) => !words || fields.some((f) => f?.toLowerCase().includes(words));
  const teams = visibleTeams(state, can.me, can.admin);
  const invitations = state.invitations.filter((i) => match(i.email));
  const members = state.members
    .filter((m) => match(m.name, m.email, m.title))
    .sort((a, b) => ROLE_ORDER[a.role] - ROLE_ORDER[b.role] || a.name.localeCompare(b.name));

  if (now === null) return null;
  return (
    <div className="flex flex-col gap-6">
      <SearchField value={q} onChange={setQ} placeholder={t("search")} label={t("search")} />
      {invitations.length > 0 ? (
        <TeamSection id="pending-invitations" title={t("pendingInvitations", { count: invitations.length })}>
          <ul className="divide-y rounded-xl border bg-card">
            {invitations.map((invitation) => (
              <InvitationRow
                key={invitation.id}
                ws={ws}
                invitation={invitation}
                me={can.me}
                members={state.members}
                canManage={can.managePeople}
                now={now}
              />
            ))}
          </ul>
        </TeamSection>
      ) : null}
      {members.length > 0 ? (
        <TeamSection id="workspace-members" title={t("membersCount", { count: members.length })}>
          <ul className="divide-y rounded-xl border bg-card">
            {members.map((member) => (
              <MemberRow
                key={member.id}
                ws={ws}
                member={member}
                me={can.me}
                teams={teams}
                now={now}
                workspaceName={state.workspace.name}
              />
            ))}
          </ul>
        </TeamSection>
      ) : (
        <EmptyMessage
          icon={FilterX}
          title={t("noMatches")}
          text={t("noMatchesHint")}
          action={
            <Button variant="outline" onClick={() => setQ("")}>
              {t("clearSearch")}
            </Button>
          }
        />
      )}
    </div>
  );
}
