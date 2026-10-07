import Link from "next/link";

import { ChevronRight, FolderKanban, Gavel, ListChecks } from "lucide-react";
import { useTranslations } from "next-intl";

import type { TeamMeeting } from "../../domain/content-contract";
import type { Member, Project, Team } from "../../domain/contract";
import { meetingPath } from "../../domain/paths";
import { VisibilityBadge } from "../shared/badges";
import { PeopleStack } from "../shared/people";
import { useMeetingWhen } from "./use-meeting-when";

type MeetingRowProps = {
  meeting: TeamMeeting;
  now: number;
  slug: string;
  meId: string;
  members: Member[];
  teams: Team[];
  projects: Project[];
  workspaceName: string;
};

/** A shared meeting: who it's shared with, when, Leo's summary and what came out of it; opens the meeting. */
export function MeetingRow({ meeting, now, slug, meId, members, teams, projects, workspaceName }: MeetingRowProps) {
  const organizer = members.find((m) => m.id === meeting.organizer_id);
  const byMe = meeting.organizer_id === meId;
  const project = projects.find((p) => p.id === meeting.project_id);
  const t = useTranslations("workspaceMeetings.row");
  const when = useMeetingWhen();
  const facts = [
    when.day(meeting.started_at, now),
    when.clock(meeting.started_at),
    when.duration(meeting.duration_minutes),
  ];
  if (organizer) facts.push(byMe ? t("recordedByYou") : t("recordedBy", { name: organizer.name }));
  if (meeting.external) facts.push(t("withGuests"));
  return (
    <li>
      <article className="group relative flex flex-col gap-2 rounded-xl border bg-card p-4 transition-colors has-[a:hover]:bg-muted/40">
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 flex-col gap-0.5">
            <h3 className="truncate font-medium" dir="auto">
              <Link
                href={meetingPath(slug, meeting.id)}
                className="outline-none after:absolute after:inset-0 after:rounded-xl focus-visible:after:ring-3 focus-visible:after:ring-ring/50"
              >
                {meeting.title}
              </Link>
            </h3>
            <p className="truncate text-muted-foreground text-xs tabular-nums">{facts.join(" · ")}</p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <VisibilityBadge
              visibility={meeting.visibility}
              teams={teams}
              workspaceName={workspaceName}
              className="hidden sm:inline-flex"
            />
            <ChevronRight
              className="size-4 text-muted-foreground transition-transform motion-reduce:transition-none ltr:group-has-[a:hover]:translate-x-0.5 rtl:-scale-x-100 rtl:group-has-[a:hover]:-translate-x-0.5"
              aria-hidden="true"
            />
          </div>
        </div>
        <p className="line-clamp-2 text-pretty text-muted-foreground text-sm" dir="auto">
          {meeting.summary}
        </p>
        <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
            <VisibilityBadge
              visibility={meeting.visibility}
              teams={teams}
              workspaceName={workspaceName}
              className="sm:hidden"
            />
            {project ? (
              <span className="inline-flex min-w-0 items-center gap-1.5">
                <FolderKanban className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
                <span className="truncate" dir="auto">
                  {project.name}
                </span>
              </span>
            ) : null}
            {meeting.decision_count > 0 ? (
              <span className="inline-flex items-center gap-1.5">
                <Gavel className="size-3.5 text-muted-foreground" aria-hidden="true" />
                {t("decisions", { count: meeting.decision_count })}
              </span>
            ) : null}
            {meeting.task_count > 0 ? (
              <span className="inline-flex items-center gap-1.5">
                <ListChecks className="size-3.5 text-muted-foreground" aria-hidden="true" />
                {t("tasks", { count: meeting.task_count })}
              </span>
            ) : null}
          </div>
          <PeopleStack names={meeting.participants.map((p) => p.name)} max={4} />
        </div>
      </article>
    </li>
  );
}
