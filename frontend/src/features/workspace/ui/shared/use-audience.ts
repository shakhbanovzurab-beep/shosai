"use client";

import { useTranslations } from "next-intl";

import type { Visibility } from "../../domain/content-contract";
import type { Team } from "../../domain/contract";
import type { KnowledgeAccess } from "../../domain/knowledge-contract";

type Audience = Visibility | KnowledgeAccess;
type Context = { teams: Team[]; workspaceName: string };

/** Who something is shared with, in the interface language: "Participants", "Engineering", "Everyone at Lumen". */
export function useAudience() {
  const t = useTranslations("workspace");
  const teamOf = (audience: Audience, teams: Team[]) => teams.find((team) => team.id === audience.team_id);

  return {
    label(audience: Audience, { teams, workspaceName }: Context) {
      if (audience.level === "participants") return t("audience.participants");
      if (audience.level === "workspace") return t("audience.everyone", { workspace: workspaceName });
      return teamOf(audience, teams)?.name ?? t("audience.aTeam");
    },
    /** "Shared with participants", "Shared with Engineering": a whole sentence for a hint or a toast. */
    sharedWith(audience: Audience, { teams, workspaceName }: Context) {
      return t("audience.sharedWith", {
        level: audience.level,
        workspace: workspaceName,
        team: teamOf(audience, teams)?.name ?? t("audience.aTeam"),
      });
    },
    /** What choosing an audience means, for a share menu. */
    hint(audience: Audience, teams: Team[]) {
      const team = teamOf(audience, teams);
      if (audience.level !== "team" || !team) return t("audience.hint", { level: audience.level });
      return t("audience.teamHint", { team: team.name, private: String(team.private) });
    },
  };
}
