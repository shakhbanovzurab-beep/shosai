"use client";

import { cn } from "cn";
import { Building2, Lock, type LucideIcon, Users } from "lucide-react";
import { useTranslations } from "use-intl";

import { Badge } from "@/components/ui/badge";

import type { Visibility } from "../../domain/content-contract";
import type { Team } from "../../domain/contract";
import { TEAM_DOT_CLASSES } from "./team-colors";
import { useAudience } from "./use-audience";

/** A team's colour as a small dot. */
export function TeamDot({ team, className }: { team: Pick<Team, "color">; className?: string }) {
  return (
    <span aria-hidden="true" className={cn("size-2 shrink-0 rounded-full", TEAM_DOT_CLASSES[team.color], className)} />
  );
}

/** A team's name with its colour; a lock marks a private team. */
export function TeamBadge({ team }: { team: Team }) {
  const t = useTranslations("workspace");
  return (
    <Badge variant="outline" className="max-w-40 font-normal">
      <TeamDot team={team} />
      <span dir="auto" className="truncate">
        {team.name}
      </span>
      {team.private ? <Lock aria-label={t("teams.private")} /> : null}
    </Badge>
  );
}

const LEVEL_ICONS: Record<Exclude<Visibility["level"], "team">, LucideIcon> = {
  participants: Users,
  workspace: Building2,
};

type VisibilityBadgeProps = {
  visibility: Visibility;
  teams: Team[];
  workspaceName: string;
  className?: string;
};

/** Who can see something, as an icon and a few words, the same in every list. */
export function VisibilityBadge({ visibility, teams, workspaceName, className }: VisibilityBadgeProps) {
  const audience = useAudience();
  const context = { teams, workspaceName };
  const label = audience.label(visibility, context);
  const team = visibility.level === "team" ? teams.find((t) => t.id === visibility.team_id) : undefined;
  let mark: React.ReactNode = team ? <TeamDot team={team} /> : null;
  if (visibility.level !== "team") {
    const Icon = LEVEL_ICONS[visibility.level];
    mark = <Icon aria-hidden="true" />;
  }
  return (
    <Badge variant="outline" className={cn("font-normal", className)}>
      {mark}
      <span className="sr-only">{audience.sharedWith(visibility, context)}</span>
      <span aria-hidden="true" dir="auto" className="truncate">
        {label}
      </span>
    </Badge>
  );
}
