"use client";

import { EllipsisVertical, Lock, Pencil, Trash2 } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { DropdownMenuItem, DropdownMenuSeparator } from "@/components/ui/dropdown-menu-items";

import type { Team, WorkspaceState } from "../../domain/contract";
import { teamMembers } from "../../domain/people";
import { setMemberTeams } from "../../model/people-actions";
import { TeamDot } from "../shared/badges";
import { PeopleStack } from "../shared/people";

type TeamCardProps = {
  ws: string;
  team: Team;
  state: WorkspaceState;
  canManage: boolean;
  onEdit: () => void;
  onDelete: () => void;
};

/** A team: what it's for, who's in it and who leads it; admins edit it, members join or leave open teams. */
export function TeamCard({ ws, team, state, canManage, onEdit, onDelete }: TeamCardProps) {
  const t = useTranslations("workspaceMembers");
  const shared = useTranslations("workspace");
  const common = useTranslations("common");
  const members = teamMembers(state, team.id);
  const me = state.members.find((m) => m.id === state.me_id);
  const inTeam = me?.team_ids.includes(team.id) ?? false;
  const lead = members.find((m) => m.id === team.lead_id);
  const count = members.length;
  let summary = t("team.members", { count });
  if (lead)
    summary =
      lead.id === state.me_id
        ? t("team.membersLedByYou", { count })
        : t("team.membersLedBy", { count, name: lead.name });

  return (
    <Card className="shadow-xs">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <TeamDot team={team} className="size-2.5" />
          <span dir="auto" className="truncate">
            {team.name}
          </span>
          {team.private ? (
            <Lock className="size-3.5 text-muted-foreground" aria-label={shared("teams.private")} />
          ) : null}
        </CardTitle>
        <CardDescription dir={team.description ? "auto" : undefined} className="line-clamp-2">
          {team.description || t("team.noDescription")}
        </CardDescription>
        {canManage ? (
          <CardAction>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon-sm" aria-label={common("actionsFor", { name: team.name })}>
                  <EllipsisVertical />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuGroup>
                  <DropdownMenuItem onSelect={onEdit}>
                    <Pencil />
                    {t("team.edit")}
                  </DropdownMenuItem>
                </DropdownMenuGroup>
                <DropdownMenuSeparator />
                <DropdownMenuGroup>
                  <DropdownMenuItem variant="destructive" onSelect={onDelete}>
                    <Trash2 />
                    {t("team.delete")}
                  </DropdownMenuItem>
                </DropdownMenuGroup>
              </DropdownMenuContent>
            </DropdownMenu>
          </CardAction>
        ) : null}
      </CardHeader>
      <CardContent className="flex items-center justify-between gap-3">
        <span className="text-muted-foreground text-sm">{summary}</span>
        {members.length > 0 ? <PeopleStack names={members.map((m) => m.name)} max={5} /> : null}
      </CardContent>
      {me && !canManage && (!team.private || inTeam) ? (
        <CardFooter>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              const next = inTeam ? me.team_ids.filter((id) => id !== team.id) : [...me.team_ids, team.id];
              const message = t(inTeam ? "team.youLeft" : "team.youJoined", { team: team.name });
              void setMemberTeams(ws, me, next, message, t);
            }}
          >
            {t(inTeam ? "team.leave" : "team.join")}
          </Button>
        </CardFooter>
      ) : null}
    </Card>
  );
}
