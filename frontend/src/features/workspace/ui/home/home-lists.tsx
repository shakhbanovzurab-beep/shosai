"use client";

import { Gavel } from "lucide-react";
import { useTranslations } from "use-intl";

import { Link } from "@/lib/navigation";

import type { Decision, Task } from "../../domain/content-contract";
import type { Project, WorkspaceState } from "../../domain/contract";
import { meetingPath, projectPath } from "../../domain/paths";
import { progressOf } from "../../domain/tasks";
import { ProjectProgress } from "../projects/project-meta";
import { QuietEmpty } from "../shared/layout";
import { useWorkspaceDates } from "../shared/use-dates";

/** The latest decisions still in force, each with the meeting it came from. */
export function RecentDecisions({ decisions, slug, now }: { decisions: Decision[]; slug: string; now: number }) {
  const t = useTranslations("workspaceHome");
  const dates = useWorkspaceDates();
  const latest = decisions
    .filter((d) => d.superseded_by === null)
    .sort((a, b) => b.decided_at.localeCompare(a.decided_at))
    .slice(0, 4);
  if (latest.length === 0) return <QuietEmpty>{t("decisions.empty")}</QuietEmpty>;

  return (
    <ul className="divide-y rounded-xl border bg-card">
      {latest.map((decision) => (
        <li key={decision.id} className="flex gap-3 px-4 py-3">
          <Gavel className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          <div className="flex min-w-0 flex-col gap-1">
            <span dir="auto" className="text-pretty text-sm">
              {decision.text}
            </span>
            <span className="truncate text-muted-foreground text-xs">
              {t.rich("decisions.source", {
                title: decision.meeting_title,
                day: dates.day(decision.decided_at, now),
                meeting: (chunks) => (
                  <Link
                    href={meetingPath(slug, decision.meeting_id)}
                    dir="auto"
                    className="underline-offset-4 hover:text-foreground hover:underline"
                  >
                    {chunks}
                  </Link>
                ),
              })}
            </span>
          </div>
        </li>
      ))}
    </ul>
  );
}

/** Active projects with how far along they are and when they're due; the ones you lead first. */
export function ActiveProjects({
  projects,
  tasks,
  state,
  slug,
  now,
}: {
  projects: Project[];
  tasks: Task[];
  state: WorkspaceState;
  slug: string;
  now: number;
}) {
  const t = useTranslations("workspaceHome");
  const dates = useWorkspaceDates();
  const active = projects
    .filter((p) => p.status === "active")
    .sort((a, b) => Number(b.lead_id === state.me_id) - Number(a.lead_id === state.me_id))
    .slice(0, 4);
  if (active.length === 0) return <QuietEmpty>{t("projects.empty")}</QuietEmpty>;

  return (
    <ul className="divide-y rounded-xl border bg-card">
      {active.map((project) => {
        const progress = progressOf(tasks.filter((t) => t.project_id === project.id));
        const lead = state.members.find((m) => m.id === project.lead_id);
        return (
          <li
            key={project.id}
            className="relative flex flex-col gap-2 px-4 py-3 transition-colors has-[a:hover]:bg-muted/40"
          >
            <div className="flex items-baseline justify-between gap-3">
              <Link
                href={projectPath(slug, project.id)}
                dir="auto"
                className="truncate font-medium text-sm outline-none after:absolute after:inset-0 focus-visible:after:ring-3 focus-visible:after:ring-ring/50"
              >
                {project.name}
              </Link>
              {project.target_date ? (
                <span className="shrink-0 text-muted-foreground text-xs">{dates.target(project.target_date, now)}</span>
              ) : null}
            </div>
            <ProjectProgress {...progress} />
            {lead ? (
              <span className="text-muted-foreground text-xs">
                {lead.id === state.me_id ? t("projects.ledByYou") : t("projects.ledBy", { name: lead.name })}
              </span>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}
