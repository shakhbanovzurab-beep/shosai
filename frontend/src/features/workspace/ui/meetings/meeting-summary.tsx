import type { ReactNode } from "react";

import { Gavel, Lightbulb, ListChecks, type LucideIcon } from "lucide-react";
import { useTranslations } from "next-intl";

import { Badge } from "@/components/ui/badge";

import type { TeamMeetingDetail } from "../../domain/content-contract";
import { useWorkspace } from "../../model/use-workspace";
import { TaskList } from "../tasks/task-groups";

function Block({ icon: Icon, title, children }: { icon: LucideIcon; title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="flex items-center gap-2 font-medium text-sm">
        <Icon className="size-4 text-muted-foreground" aria-hidden="true" />
        {title}
      </h2>
      {children}
    </section>
  );
}

/** Leo's notes on a meeting: the summary, key points, decisions and the tasks agreed in it. */
export function MeetingSummary({ meeting, now }: { meeting: TeamMeetingDetail; now: number }) {
  const { ws, slug, state } = useWorkspace();
  const t = useTranslations("workspaceMeetings.meeting");
  return (
    <div className="flex flex-col gap-8">
      <section className="flex flex-col gap-2" aria-labelledby="meeting-summary-heading">
        <h2 id="meeting-summary-heading" className="font-medium text-muted-foreground text-xs uppercase tracking-wide">
          {t("summary")}
        </h2>
        <p className="text-pretty text-sm leading-relaxed" dir="auto">
          {meeting.summary}
        </p>
      </section>

      {meeting.key_points.length > 0 ? (
        <Block icon={Lightbulb} title={t("keyPoints")}>
          <ul className="flex list-disc flex-col gap-1.5 ps-5 text-sm marker:text-muted-foreground">
            {meeting.key_points.map((point) => (
              <li key={point} dir="auto">
                {point}
              </li>
            ))}
          </ul>
        </Block>
      ) : null}

      {meeting.decisions.length > 0 ? (
        <Block icon={Gavel} title={t("decisions")}>
          <ul className="flex flex-col gap-1.5 text-sm">
            {meeting.decisions.map((decision) => (
              <li
                key={decision.id}
                className="flex items-start justify-between gap-3 rounded-lg border bg-card px-3 py-2"
              >
                <span dir="auto" className={decision.superseded_by ? "text-muted-foreground line-through" : undefined}>
                  {decision.text}
                </span>
                {decision.superseded_by ? (
                  <Badge variant="secondary" className="shrink-0">
                    {t("replacedLater")}
                  </Badge>
                ) : null}
              </li>
            ))}
          </ul>
        </Block>
      ) : null}

      {meeting.tasks.length > 0 ? (
        <Block icon={ListChecks} title={t("tasks")}>
          <TaskList
            items={meeting.tasks}
            ws={ws}
            slug={slug}
            now={now}
            meId={state.me_id}
            members={state.members}
            teams={[]}
            projects={state.projects}
            showOwner
            hideSource="meeting"
          />
        </Block>
      ) : null}
    </div>
  );
}
