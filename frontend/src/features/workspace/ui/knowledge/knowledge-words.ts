"use client";

import { differenceInCalendarDays, isSameYear, parseISO } from "date-fns";
import type { useFormatter, useTranslations } from "next-intl";

import type { Member, Team } from "../../domain/contract";
import type { KnowledgeAccess, KnowledgeItem } from "../../domain/knowledge-contract";
import { accessAudiences, accessKey } from "../../domain/visibility";

/** The `workspaceKnowledge` translator, passed into the plain helpers below. */
export type KnowledgeWords = ReturnType<typeof useTranslations<"workspaceKnowledge">>;
type Formatter = ReturnType<typeof useFormatter>;

/**
 * Who added a piece of knowledge, as the messages' `who` select reads it: you, a member (by name), or
 * someone who has since left the workspace.
 */
export type Who = { who: "me" | "member" | "former"; name: string };

export function whoAdded(item: KnowledgeItem, members: Member[], meId: string): Who {
  const member = members.find((m) => m.id === item.added_by);
  if (!member) return { who: "former", name: "" };
  return member.id === meId ? { who: "me", name: member.name } : { who: "member", name: member.name };
}

/** "Everyone at Lumen", or the team's name. */
export function accessText(t: KnowledgeWords, access: KnowledgeAccess, teams: Team[], workspace: string) {
  if (access.level === "workspace") return t("access.everyone", { workspace });
  return teams.find((team) => team.id === access.team_id)?.name ?? t("access.someTeam");
}

/** The audiences a member may pick: everyone first, then their teams (every team for admins). */
export function accessChoices(
  t: KnowledgeWords,
  teams: Team[],
  workspace: string,
  me: Pick<Member, "team_ids">,
  admin: boolean,
) {
  return accessAudiences(teams, me, admin).map((access) => ({
    key: accessKey(access),
    label:
      access.level === "workspace"
        ? t("access.everyone", { workspace })
        : (teams.find((team) => team.id === access.team_id)?.name ?? ""),
  }));
}

/** Who owns it, in a few words: the workspace (an upload or a source), or whoever shared their file. */
export function originText(t: KnowledgeWords, item: KnowledgeItem, who: Who, workspace: string) {
  if (item.source.kind === "personal") return t("origin.personal", who);
  if (item.source.kind === "connector") return t("origin.connector", who);
  return t("origin.upload", { ...who, workspace });
}

/**
 * When it was added, as the row's last fact: "Today", "5 days ago", then the date. Days count in the
 * viewer's calendar, as `now` does; the date itself is formatted in UTC like the rest of the demo data.
 */
export function addedText(t: KnowledgeWords, format: Formatter, iso: string, now: number) {
  const date = parseISO(iso);
  const days = Math.max(0, differenceInCalendarDays(now, date));
  if (days < 30) return t("added", { days });
  return format.dateTime(date, isSameYear(date, now) ? "short" : "medium");
}
