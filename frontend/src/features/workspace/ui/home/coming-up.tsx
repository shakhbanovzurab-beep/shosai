"use client";

import { Lock } from "lucide-react";
import { useTranslations } from "use-intl";

import { Badge } from "@/components/ui/badge";
import { useTimeZone } from "@/i18n/time-zone";

import type { UpcomingMeeting } from "../../domain/content-contract";
import type { WorkspaceState } from "../../domain/contract";
import { daysFromToday } from "../../domain/format";
import { TeamDot } from "../shared/badges";
import { QuietEmpty } from "../shared/layout";
import { useAudience } from "../shared/use-audience";
import { useWorkspaceDates } from "../shared/use-dates";

/** Where a meeting's notes will go once it ends: shown before, so nobody is surprised after. */
function SharesWith({ meeting, state }: { meeting: UpcomingMeeting; state: WorkspaceState }) {
  const t = useTranslations("workspaceHome");
  const audience = useAudience();
  if (meeting.external || meeting.shares_with === null)
    return (
      <span className="inline-flex items-center gap-1.5">
        <Lock className="size-3" aria-hidden="true" />
        {t(meeting.external ? "comingUp.guestsPrivate" : "comingUp.private")}
      </span>
    );
  const sharesWith = meeting.shares_with;
  const team = state.teams.find((item) => item.id === sharesWith.team_id);
  return (
    <span className="inline-flex min-w-0 items-center gap-1.5">
      {team ? <TeamDot team={team} /> : null}
      <span className="truncate">
        {t("comingUp.notesGoTo", {
          audience: audience.label(sharesWith, { teams: state.teams, workspaceName: state.workspace.name }),
        })}
      </span>
    </span>
  );
}

/** The member's next team meetings, live first, and where each one's notes will be shared. */
export function ComingUp({
  upcoming,
  state,
  now,
}: {
  upcoming: UpcomingMeeting[];
  state: WorkspaceState;
  now: number;
}) {
  const t = useTranslations("workspaceHome");
  const dates = useWorkspaceDates();
  const zone = useTimeZone();
  const next = upcoming
    .filter((m) => Date.parse(m.end) > now)
    .sort((a, b) => a.start.localeCompare(b.start))
    .slice(0, 4);
  if (next.length === 0) return <QuietEmpty>{t("comingUp.empty")}</QuietEmpty>;

  return (
    <ul className="divide-y rounded-xl border bg-card">
      {next.map((meeting) => {
        const live = Date.parse(meeting.start) <= now;
        const today = daysFromToday(meeting.start, now, zone) === 0;
        return (
          <li key={meeting.id} className="flex gap-3 px-4 py-3">
            <div className="flex w-16 shrink-0 flex-col">
              {live ? (
                <Badge variant="destructive" className="w-fit">
                  {t("comingUp.live")}
                </Badge>
              ) : (
                <span className="font-medium text-sm tabular-nums">{dates.clock(meeting.start)}</span>
              )}
              {today ? null : <span className="text-muted-foreground text-xs">{dates.day(meeting.start, now)}</span>}
            </div>
            <div className="flex min-w-0 flex-1 flex-col gap-1">
              <span dir="auto" className="truncate font-medium text-sm">
                {meeting.title}
              </span>
              <span className="truncate text-muted-foreground text-xs">
                <SharesWith meeting={meeting} state={state} />
              </span>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
