"use client";

import { useState } from "react";

import { FolderKanban, Plus } from "lucide-react";
import { useFormatter, useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { useNow } from "@/hooks/use-now";
import { CALENDAR_DAY } from "@/i18n/calendar-days";
import { useTimeZone } from "@/i18n/time-zone";
import { Link } from "@/lib/navigation";

import type { Task } from "../../domain/content-contract";
import type { Project } from "../../domain/contract";
import { daysFromToday, isThisYear } from "../../domain/format";
import { projectPath } from "../../domain/paths";
import { progressOf } from "../../domain/tasks";
import { useTasks, useWorkspace } from "../../model/use-workspace";
import { TeamDot } from "../shared/badges";
import { EmptyMessage } from "../shared/empty-message";
import { TeamPage, TeamPageHeader } from "../shared/layout";
import { ProjectDialog } from "./project-dialog";
import { ProjectProgress, ProjectStatusBadge } from "./project-meta";

const ORDER: Record<Project["status"], number> = { active: 0, planned: 1, paused: 2, completed: 3 };

/**
 * "Overdue · Oct 3", "Target today", "Target Fri", "Target Oct 20". Дни считаются от сегодня в поясе кабинета;
 * цель — календарный день, полночь UTC, и печатается в UTC.
 */
function useTargetLabel(now: number) {
  const t = useTranslations("workspaceProjects");
  const format = useFormatter();
  const zone = useTimeZone();
  return (day: string) => {
    const date = new Date(day);
    const days = daysFromToday(day, now, zone);
    const sameYear = isThisYear(day, now, zone);
    if (days < 0) return t("target.overdue", { date: format.dateTime(date, "short", CALENDAR_DAY) });
    if (days === 0) return t("target.today");
    if (days === 1) return t("target.tomorrow");
    if (days < 7) return t("target.on", { date: format.dateTime(date, { weekday: "short", ...CALENDAR_DAY }) });
    return t("target.on", { date: format.dateTime(date, sameYear ? "short" : "medium", CALENDAR_DAY) });
  };
}

function ProjectRow({ project, tasks, now }: { project: Project; tasks: Task[] | null; now: number }) {
  const { slug, state } = useWorkspace();
  const t = useTranslations("workspaceProjects");
  const targetLabel = useTargetLabel(now);
  const lead = state.members.find((m) => m.id === project.lead_id);
  const team = state.teams.find((t) => t.id === project.team_id);
  return (
    <li className="relative grid gap-3 px-4 py-3.5 transition-colors has-[a:hover]:bg-muted/40 md:grid-cols-[minmax(0,1fr)_12rem_9rem] md:items-center">
      <div className="flex min-w-0 flex-col gap-1">
        <div className="flex min-w-0 items-center gap-2">
          <Link
            href={projectPath(slug, project.id)}
            dir="auto"
            className="truncate font-medium outline-none after:absolute after:inset-0 focus-visible:after:ring-3 focus-visible:after:ring-ring/50"
          >
            {project.name}
          </Link>
          <ProjectStatusBadge status={project.status} />
        </div>
        <span className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 text-muted-foreground text-xs">
          {lead ? <span>{t("ledBy", { who: lead.id === state.me_id ? "me" : "member", name: lead.name })}</span> : null}
          {team ? (
            <span className="inline-flex items-center gap-1.5">
              <TeamDot team={team} />
              <span dir="auto">{team.name}</span>
            </span>
          ) : null}
        </span>
      </div>
      {tasks ? (
        <ProjectProgress {...progressOf(tasks.filter((t) => t.project_id === project.id))} />
      ) : (
        <Skeleton className="h-1.5" />
      )}
      <span className="text-muted-foreground text-xs md:text-end">
        {project.target_date && project.status !== "completed" ? targetLabel(project.target_date) : t("target.none")}
      </span>
    </li>
  );
}

/** The workspace's projects, active first: the shared context their meetings, decisions and tasks belong to. */
export function ProjectsScreen() {
  const { state } = useWorkspace();
  const t = useTranslations("workspaceProjects");
  const tasks = useTasks();
  const now = useNow();
  const [filter, setFilter] = useState<"open" | "all">("open");
  const [creating, setCreating] = useState(false);
  const shown = state.projects
    .filter((p) => filter === "all" || p.status !== "completed")
    .toSorted((a, b) => ORDER[a.status] - ORDER[b.status] || a.name.localeCompare(b.name));
  const newButton = (
    <Button onClick={() => setCreating(true)}>
      <Plus data-icon="inline-start" />
      {t("newProject")}
    </Button>
  );

  return (
    <TeamPage>
      <TeamPageHeader title={t("title")} description={t("description")} actions={newButton} />
      {state.projects.length === 0 ? (
        <EmptyMessage icon={FolderKanban} title={t("empty.title")} text={t("empty.text")} action={newButton} />
      ) : (
        <>
          <ToggleGroup
            type="single"
            variant="outline"
            spacing={0}
            value={filter}
            onValueChange={(value) => (value === "open" || value === "all" ? setFilter(value) : undefined)}
            aria-label={t("filter.label")}
          >
            <ToggleGroupItem value="open" className="px-3">
              {t("filter.open")}
            </ToggleGroupItem>
            <ToggleGroupItem value="all" className="px-3">
              {t("filter.all")}
            </ToggleGroupItem>
          </ToggleGroup>
          {now === null ? null : (
            <ul className="divide-y rounded-xl border bg-card">
              {shown.map((project) => (
                <ProjectRow
                  key={project.id}
                  project={project}
                  tasks={tasks.status === "ready" ? tasks.data.tasks : null}
                  now={now}
                />
              ))}
            </ul>
          )}
        </>
      )}
      <ProjectDialog project={null} open={creating} onOpenChange={setCreating} />
    </TeamPage>
  );
}
