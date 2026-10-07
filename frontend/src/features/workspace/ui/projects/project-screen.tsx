"use client";

import { type ReactNode, useState } from "react";

import Link from "next/link";

import { ArrowLeft, FolderX, Plus } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { useNow } from "@/hooks/use-now";

import { progressOf } from "../../domain/tasks";
import { useDecisions, useMeetings, useResources, useTasks, useWorkspace } from "../../model/use-workspace";
import { RecentDecisions } from "../home/home-lists";
import { MeetingRow } from "../meetings/meeting-row";
import { BlockState } from "../shared/block-state";
import { EmptyMessage } from "../shared/empty-message";
import { QuietEmpty, TeamPage, TeamSection } from "../shared/layout";
import { NewTaskDialog } from "../tasks/new-task-dialog";
import { TaskGroups } from "../tasks/task-groups";
import { ProjectFiles } from "./project-files";
import { ProjectHeader } from "./project-header";
import { ProjectProgress } from "./project-meta";

/** One project: where it stands, its tasks, the meetings that shaped it, what was decided and its files. */
export function ProjectScreen({ projectId, picker }: { projectId: string; picker?: ReactNode }) {
  const { ws, slug, state, path } = useWorkspace();
  const t = useTranslations("workspaceProjects");
  const resources = useResources();
  const tasks = useTasks();
  const meetings = useMeetings();
  const decisions = useDecisions();
  const now = useNow();
  const [adding, setAdding] = useState(false);
  const project = state.projects.find((p) => p.id === projectId);
  const back = (
    <Button variant="ghost" size="sm" className="-ms-2 w-fit text-muted-foreground" asChild>
      <Link href={path("/projects")}>
        <ArrowLeft data-icon="inline-start" className="rtl:-scale-x-100" />
        {t("title")}
      </Link>
    </Button>
  );

  if (!project)
    return (
      <TeamPage>
        {back}
        <EmptyMessage
          icon={FolderX}
          title={t("notFound.title")}
          text={t("notFound.text")}
          action={
            <Button asChild variant="outline">
              <Link href={path("/projects")}>{t("notFound.action")}</Link>
            </Button>
          }
        />
      </TeamPage>
    );
  if (now === null) return null;
  const ctx = {
    ws,
    slug,
    now,
    meId: state.me_id,
    members: state.members,
    teams: state.teams,
    projects: state.projects,
  };

  return (
    <TeamPage>
      {back}
      <ProjectHeader project={project} />
      <BlockState state={tasks} what="tasks" height="h-64" onRetry={() => void resources.tasks.refresh()}>
        {(data) => {
          const mine = data.tasks.filter((t) => t.project_id === project.id);
          return (
            <>
              <ProjectProgress {...progressOf(mine)} className="max-w-md" />
              <TeamSection
                id="project-tasks"
                title={t("sections.tasks")}
                action={
                  <Button variant="outline" size="sm" onClick={() => setAdding(true)}>
                    <Plus data-icon="inline-start" />
                    {t("sections.addTask")}
                  </Button>
                }
              >
                {mine.length === 0 ? (
                  <QuietEmpty>{t("sections.tasksEmpty")}</QuietEmpty>
                ) : (
                  <TaskGroups items={mine} showOwner hideSource="project" {...ctx} />
                )}
              </TeamSection>
            </>
          );
        }}
      </BlockState>
      <div className="grid items-start gap-8 lg:grid-cols-2">
        <TeamSection id="project-meetings" title={t("sections.meetings")}>
          <BlockState state={meetings} what="meetings" onRetry={() => void resources.meetings.refresh()}>
            {(data) => {
              const linked = data.meetings.filter((m) => m.project_id === project.id);
              if (linked.length === 0) return <QuietEmpty>{t("sections.meetingsEmpty")}</QuietEmpty>;
              return (
                <ul className="flex flex-col gap-3">
                  {linked.map((meeting) => (
                    <MeetingRow
                      key={meeting.id}
                      meeting={meeting}
                      now={now}
                      slug={slug}
                      meId={state.me_id}
                      members={state.members}
                      teams={state.teams}
                      projects={[]}
                      workspaceName={state.workspace.name}
                    />
                  ))}
                </ul>
              );
            }}
          </BlockState>
        </TeamSection>
        <TeamSection id="project-decisions" title={t("sections.decisions")}>
          <BlockState state={decisions} what="decisions" onRetry={() => void resources.decisions.refresh()}>
            {(data) => (
              <RecentDecisions
                decisions={data.decisions.filter((d) => d.project_id === project.id)}
                slug={slug}
                now={now}
              />
            )}
          </BlockState>
        </TeamSection>
      </div>
      <ProjectFiles project={project} now={now} picker={picker} />
      <NewTaskDialog open={adding} onOpenChange={setAdding} projectId={project.id} />
    </TeamPage>
  );
}
