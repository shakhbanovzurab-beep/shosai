import { cn } from "cn";
import { differenceInCalendarDays, isSameYear, parseISO } from "date-fns";
import { CornerDownRight, Gavel } from "lucide-react";
import { useFormatter, useTranslations } from "use-intl";

import { Badge } from "@/components/ui/badge";
import { Link } from "@/lib/navigation";

import type { Decision } from "../../domain/content-contract";
import type { Team } from "../../domain/contract";
import { meetingPath } from "../../domain/paths";
import { TeamDot } from "../shared/badges";
import { PeopleStack } from "../shared/people";

/**
 * "Today", "Yesterday", "Tomorrow", "Mon, Oct 5", or "Oct 5, 2025" in another year. Days count in the viewer's
 * calendar, as `now` does; the date is formatted in UTC, like the demo timestamps.
 */
function useDayLabel(now: number) {
  const t = useTranslations("workspaceDecisions");
  const format = useFormatter();
  return (iso: string) => {
    const date = parseISO(iso);
    const days = differenceInCalendarDays(date, now);
    if (days === 0) return t("day.today");
    if (days === -1) return t("day.yesterday");
    if (days === 1) return t("day.tomorrow");
    return isSameYear(date, now)
      ? format.dateTime(date, { weekday: "short", month: "short", day: "numeric" })
      : format.dateTime(date, "medium");
  };
}

/** A decision as the log shows it: what was decided, where and when, and what replaced it if anything did. */
export function DecisionItem({
  decision,
  replacement,
  teams,
  slug,
  now,
}: {
  decision: Decision;
  replacement: Decision | undefined;
  teams: Team[];
  slug: string;
  now: number;
}) {
  const t = useTranslations("workspaceDecisions");
  const dayLabel = useDayLabel(now);
  const meetingHref = (id: string) => meetingPath(slug, id);
  const team = teams.find((t) => t.id === decision.team_id);
  const replaced = decision.superseded_by !== null;
  return (
    <li className="flex gap-3 rounded-xl border bg-card p-4">
      <span className="grid size-8 shrink-0 place-items-center rounded-lg border bg-muted">
        <Gavel className="size-4 text-muted-foreground" aria-hidden="true" />
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1">
          <p dir="auto" className={cn("text-pretty font-medium", replaced && "text-muted-foreground line-through")}>
            {decision.text}
          </p>
          {replaced ? <Badge variant="secondary">{t("replaced")}</Badge> : null}
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 text-muted-foreground text-xs">
            <Link
              href={meetingHref(decision.meeting_id)}
              dir="auto"
              className="truncate font-medium text-foreground underline-offset-4 hover:underline"
            >
              {decision.meeting_title}
            </Link>
            <time dateTime={decision.decided_at}>{dayLabel(decision.decided_at)}</time>
            {team ? (
              <span className="inline-flex items-center gap-1.5">
                <TeamDot team={team} />
                <span dir="auto">{team.name}</span>
              </span>
            ) : null}
          </div>
          <PeopleStack names={decision.participants} max={4} />
        </div>
        {replaced ? (
          <p className="flex items-start gap-1.5 text-muted-foreground text-xs">
            <CornerDownRight className="mt-px size-3.5 shrink-0 rtl:-scale-x-100" aria-hidden="true" />
            {replacement ? (
              <span>
                {t.rich("replacedBy", {
                  decision: replacement.text,
                  meeting: replacement.meeting_title,
                  link: (chunks) => (
                    <Link
                      href={meetingHref(replacement.meeting_id)}
                      dir="auto"
                      className="text-foreground underline-offset-4 hover:underline"
                    >
                      {chunks}
                    </Link>
                  ),
                })}
              </span>
            ) : (
              <span>{t("replacedHidden")}</span>
            )}
          </p>
        ) : null}
      </div>
    </li>
  );
}
