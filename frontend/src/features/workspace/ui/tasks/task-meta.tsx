import Link from "next/link";

import { FolderKanban, Video } from "lucide-react";
import { useTranslations } from "next-intl";

import { Badge } from "@/components/ui/badge";

import type { Task } from "../../domain/content-contract";
import type { Project, Team } from "../../domain/contract";
import { meetingPath, projectPath } from "../../domain/paths";
import { TeamDot } from "../shared/badges";

const LINK = "inline-flex min-w-0 items-center gap-1 underline-offset-4 hover:text-foreground hover:underline";

/** Under a task's title: in progress or not, and where it came from (project, meeting, team). */
export function TaskMeta({
  task,
  slug,
  teams,
  projects,
  hideSource,
}: {
  task: Task;
  slug: string;
  teams: Team[];
  projects: Project[];
  hideSource?: "meeting" | "project";
}) {
  const t = useTranslations("workspaceTasks.status");
  const team = teams.find((t) => t.id === task.team_id);
  const project = hideSource === "project" ? undefined : projects.find((p) => p.id === task.project_id);
  const meetingId = hideSource === "meeting" || task.meeting_title === null ? null : task.meeting_id;
  const busy = task.status === "in_progress";
  if (!busy && !project && !meetingId && !team) return null;

  return (
    <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 text-muted-foreground text-xs">
      {busy ? <Badge variant="secondary">{t("in_progress")}</Badge> : null}
      {project ? (
        <Link href={projectPath(slug, project.id)} className={LINK}>
          <FolderKanban className="size-3 shrink-0" aria-hidden="true" />
          <span className="truncate" dir="auto">
            {project.name}
          </span>
        </Link>
      ) : null}
      {meetingId ? (
        <Link href={meetingPath(slug, meetingId)} className={LINK}>
          <Video className="size-3 shrink-0" aria-hidden="true" />
          <span className="truncate" dir="auto">
            {task.meeting_title}
          </span>
        </Link>
      ) : null}
      {team ? (
        <span className="inline-flex items-center gap-1.5">
          <TeamDot team={team} />
          <span dir="auto">{team.name}</span>
        </span>
      ) : null}
    </div>
  );
}
