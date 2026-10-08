"use client";

import { useState } from "react";

import { cn } from "cn";
import { EllipsisVertical, UserMinus, Users } from "lucide-react";
import { useTranslations } from "next-intl";

import { ConfirmDestructive } from "@/components/feedback";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { DropdownMenuCheckboxItem, DropdownMenuItem, DropdownMenuSeparator } from "@/components/ui/dropdown-menu-items";
import { DropdownMenuSub, DropdownMenuSubContent, DropdownMenuSubTrigger } from "@/components/ui/dropdown-menu-sub";

import type { Member, Team } from "../../domain/contract";
import { IDLE_DAYS, isIdle, lastActive } from "../../domain/format";
import { firstName } from "../../domain/people";
import { canManageMember } from "../../domain/roles";
import { changeRole, removeMember, setMemberTeams } from "../../model/people-actions";
import { TeamBadge } from "../shared/badges";
import { PersonAvatar } from "../shared/people";
import { useWorkspaceDates } from "../shared/use-dates";
import { RoleSelect, RoleText } from "./role-select";

type MemberRowProps = { ws: string; member: Member; me: Member; teams: Team[]; now: number; workspaceName: string };

/** A member: who they are, their teams, role and last activity; admins change roles and teams in place. */
export function MemberRow({ ws, member, me, teams, now, workspaceName }: MemberRowProps) {
  const t = useTranslations("workspaceMembers");
  const common = useTranslations("common");
  const dates = useWorkspaceDates();
  const [removing, setRemoving] = useState(false);
  const manage = canManageMember(me, member);
  const inTeam = new Set(member.team_ids);
  const theirTeams = teams.filter((t) => inTeam.has(t.id));
  const idle = isIdle(member.last_active_at, now);

  const toggleTeam = (team: Team, on: boolean) => {
    const next = on ? [...member.team_ids, team.id] : member.team_ids.filter((id) => id !== team.id);
    const name = firstName(member.name);
    const message = t(on ? "member.joinedTeam" : "member.leftTeam", { name, team: team.name });
    void setMemberTeams(ws, member, next, message, t);
  };

  return (
    <li className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
      <div className="flex min-w-0 flex-1 basis-60 items-center gap-3">
        <PersonAvatar name={member.name} size="default" />
        <div className="flex min-w-0 flex-col">
          <span className="flex items-center gap-2 font-medium text-sm">
            <span dir="auto" className="truncate">
              {member.name}
            </span>
            {member.id === me.id ? <Badge variant="secondary">{t("member.you")}</Badge> : null}
          </span>
          <span dir="auto" className="truncate text-muted-foreground text-xs">
            {member.title ? t("member.titleAndEmail", { title: member.title, email: member.email }) : member.email}
          </span>
        </div>
      </div>
      <div className="hidden min-w-0 flex-wrap gap-1.5 lg:flex lg:w-56">
        {theirTeams.map((team) => (
          <TeamBadge key={team.id} team={team} />
        ))}
      </div>
      <span
        className={cn("hidden w-28 text-xs md:block", idle ? "text-foreground" : "text-muted-foreground")}
        title={idle ? t("member.idle", { days: IDLE_DAYS }) : undefined}
      >
        {dates.lastActive(lastActive(member.last_active_at, now))}
      </span>
      <div className="ms-auto flex items-center gap-1">
        {manage && member.role !== "owner" ? (
          <RoleSelect
            value={member.role}
            onChange={(role) => void changeRole(ws, member, role, t)}
            label={t("member.roleOf", { name: member.name })}
            className="w-28"
          />
        ) : (
          <RoleText role={member.role} />
        )}
        {manage ? (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon-sm" aria-label={common("actionsFor", { name: member.name })}>
                <EllipsisVertical />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              {teams.length > 0 ? (
                <>
                  <DropdownMenuGroup>
                    <DropdownMenuSub>
                      <DropdownMenuSubTrigger>
                        <Users />
                        {t("tabs.teams")}
                      </DropdownMenuSubTrigger>
                      <DropdownMenuSubContent className="w-52">
                        {teams.map((team) => (
                          <DropdownMenuCheckboxItem
                            key={team.id}
                            checked={inTeam.has(team.id)}
                            onCheckedChange={(on) => toggleTeam(team, on === true)}
                            onSelect={(event) => event.preventDefault()}
                          >
                            <span dir="auto">{team.name}</span>
                          </DropdownMenuCheckboxItem>
                        ))}
                      </DropdownMenuSubContent>
                    </DropdownMenuSub>
                  </DropdownMenuGroup>
                  <DropdownMenuSeparator />
                </>
              ) : null}
              <DropdownMenuGroup>
                <DropdownMenuItem variant="destructive" onSelect={() => setRemoving(true)}>
                  <UserMinus />
                  {t("member.remove")}
                </DropdownMenuItem>
              </DropdownMenuGroup>
            </DropdownMenuContent>
          </DropdownMenu>
        ) : (
          <span className="size-7" aria-hidden="true" />
        )}
      </div>
      <ConfirmDestructive
        open={removing}
        title={t("member.removeTitle", { name: member.name, workspace: workspaceName })}
        description={t("member.removeDescription", { name: firstName(member.name) })}
        confirmLabel={common("actions.remove")}
        onConfirm={() => {
          setRemoving(false);
          void removeMember(ws, member, t);
        }}
        onCancel={() => setRemoving(false)}
      />
    </li>
  );
}
