"use client";

import { type ReactNode, useState } from "react";

import { useTranslations } from "use-intl";

import { LoadError } from "@/components/feedback";
import { Skeleton } from "@/components/ui/skeleton";
import { useNow } from "@/hooks/use-now";

import { visibleTeams } from "../../domain/people";
import { useKnowledge, useResources, useWorkspace } from "../../model/use-workspace";
import { SearchField, TeamFilter } from "../shared/filters";
import { TeamPage, TeamPageHeader } from "../shared/layout";
import { AddKnowledgeMenu } from "./add-knowledge-menu";
import { AlwaysIncluded } from "./always-included";
import { KnowledgeSections } from "./knowledge-sections";

/**
 * What Leo knows in the workspace: meetings, decisions and projects on their own, plus files and
 * sources people add. Each person gets answers only from what they can use.
 */
export function TeamKnowledgeScreen({ picker }: { picker?: ReactNode }) {
  const { ws, slug, state, can } = useWorkspace();
  const t = useTranslations("workspaceKnowledge");
  const knowledge = useKnowledge();
  const resources = useResources();
  const now = useNow();
  const [team, setTeam] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const name = state.workspace.name;
  const addMenu = <AddKnowledgeMenu picker={picker} />;
  const ready = knowledge.status === "ready" && now !== null;
  const all = knowledge.status === "ready" ? knowledge.data.items : [];
  const words = q.trim().toLowerCase();
  const shown = all.filter(
    (item) => (!team || item.access.team_id === team) && (!words || item.name.toLowerCase().includes(words)),
  );

  return (
    <TeamPage>
      <TeamPageHeader title={t("title")} description={t("description", { workspace: name })} actions={addMenu} />
      <AlwaysIncluded />
      {all.length > 0 ? (
        <div className="flex flex-col gap-2 sm:flex-row">
          <SearchField value={q} onChange={setQ} placeholder={t("search.placeholder")} label={t("search.label")} />
          <TeamFilter teams={visibleTeams(state, can.me, can.admin)} value={team} onChange={setTeam} />
        </div>
      ) : null}
      {knowledge.status === "error" ? (
        <LoadError
          title={t("loadFailed")}
          message={knowledge.message}
          onRetry={() => void resources.knowledge.refresh()}
        />
      ) : null}
      {knowledge.status !== "error" && !ready ? (
        <Skeleton className="h-64 rounded-xl" aria-label={t("loading")} />
      ) : null}
      {ready ? (
        <KnowledgeSections
          all={all}
          shown={shown}
          ctx={{
            ws,
            slug,
            now,
            me: can.me,
            admin: can.admin,
            members: state.members,
            teams: state.teams,
            projects: state.projects,
            workspaceName: name,
          }}
          addMenu={addMenu}
          onClearFilters={() => {
            setTeam(null);
            setQ("");
          }}
        />
      ) : null}
    </TeamPage>
  );
}
