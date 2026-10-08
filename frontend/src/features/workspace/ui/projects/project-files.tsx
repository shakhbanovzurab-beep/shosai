"use client";

import type { ReactNode } from "react";

import { useTranslations } from "use-intl";

import type { Project } from "../../domain/contract";
import { useKnowledge, useResources, useWorkspace } from "../../model/use-workspace";
import { AddKnowledgeMenu } from "../knowledge/add-knowledge-menu";
import { type KnowledgeCtx, KnowledgeRow } from "../knowledge/knowledge-row";
import { BlockState } from "../shared/block-state";
import { QuietEmpty, TeamSection } from "../shared/layout";

/** The files and sources that belong to a project, the ones Leo uses when asked about it. */
export function ProjectFiles({ project, now, picker }: { project: Project; now: number; picker?: ReactNode }) {
  const { ws, slug, state, can } = useWorkspace();
  const t = useTranslations("workspaceProjects");
  const knowledge = useKnowledge();
  const resources = useResources();
  const ctx: KnowledgeCtx = {
    ws,
    slug,
    now,
    me: can.me,
    admin: can.admin,
    members: state.members,
    teams: state.teams,
    projects: state.projects,
    workspaceName: state.workspace.name,
  };

  return (
    <TeamSection
      id="project-files"
      title={t("sections.files")}
      action={<AddKnowledgeMenu picker={picker} projectId={project.id} size="sm" />}
    >
      <BlockState state={knowledge} what="files" onRetry={() => void resources.knowledge.refresh()}>
        {(data) => {
          const files = data.items.filter((k) => k.project_id === project.id);
          if (files.length === 0) return <QuietEmpty>{t("sections.filesEmpty")}</QuietEmpty>;
          return (
            <ul
              className="divide-y rounded-xl border bg-card"
              aria-label={t("sections.filesLabel", { project: project.name })}
            >
              {files.map((item) => (
                <KnowledgeRow key={item.id} item={item} ctx={ctx} showProject={false} />
              ))}
            </ul>
          );
        }}
      </BlockState>
    </TeamSection>
  );
}
