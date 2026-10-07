"use client";

import { useTranslations } from "next-intl";

import type { Visibility } from "../../domain/content-contract";
import type { Member, Team } from "../../domain/contract";
import { shareAudiences } from "../../domain/visibility";

type Context = { teams: Team[]; workspaceName: string };

/**
 * Who sees a shared meeting, in words: the audiences of a share menu with their hints, and the "Shared
 * with …" phrase of buttons and toasts. The domain only decides which audiences there are.
 */
export function useAudienceWords({ teams, workspaceName }: Context) {
  const t = useTranslations("workspaceMeetings.audience");
  const teamOf = (v: Visibility) => teams.find((team) => team.id === v.team_id);
  const label = (v: Visibility) => {
    if (v.level === "participants") return t("participants");
    if (v.level === "workspace") return t("workspace", { workspace: workspaceName });
    return teamOf(v)?.name ?? t("unknownTeam");
  };
  const hint = (v: Visibility) => {
    if (v.level !== "team") return t(v.level === "participants" ? "participantsHint" : "workspaceHint");
    const team = teamOf(v);
    const name = team?.name ?? t("unknownTeam");
    return t(team?.private ? "privateTeamHint" : "teamHint", { team: name });
  };
  const args = (v: Visibility) => ({ level: v.level, workspace: workspaceName, team: label(v) });

  return {
    label,
    /** "Shared with Engineering", for the share button and its toasts. */
    sharedWith: (v: Visibility) => t("sharedWith", args(v)),
    /** "“Roadmap sync” is shared with everyone at Lumen", once a recording is shared. */
    sharedToast: (v: Visibility, title: string) => t("sharedToast", { ...args(v), title }),
    /** The audiences one member may pick, narrowest first, each with what it means. */
    options: (me: Pick<Member, "team_ids">, admin: boolean) =>
      shareAudiences(teams, me, admin).map((visibility) => ({
        visibility,
        label: label(visibility),
        description: hint(visibility),
      })),
  };
}
