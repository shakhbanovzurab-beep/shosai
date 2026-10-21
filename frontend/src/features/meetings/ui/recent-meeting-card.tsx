import { ChevronRight, Gavel, ListChecks } from "lucide-react";
import { useTranslations } from "use-intl";

import { RecordingShareBadge } from "@/features/workspace/ui/personal/shared-meetings";
import { Link } from "@/lib/navigation";

import type { Meeting } from "../domain/meeting";
import { MeetingParticipants, MeetingSourceLabel } from "./meeting-meta";
import { useMeetingTimes } from "./use-meeting-times";

/** A finished meeting with Leo's recap: the summary, how many tasks and decisions; opens its notes. */
export function RecentMeetingCard({ meeting, now }: { meeting: Meeting; now: number }) {
  const t = useTranslations("meetings");
  const times = useMeetingTimes();
  const { recap } = meeting;
  // Страница встречи в «Заметках»: у записи она есть и до того, как Leo написал итог.
  const noteId = recap?.noteId ?? meeting.recording?.noteId;
  const when = t("recap.when", {
    day: times.day(meeting.start, now),
    time: times.range(meeting),
    duration: times.duration(meeting),
  });
  return (
    <article className="group relative flex flex-col gap-3 rounded-xl border bg-card p-4 transition-colors has-[a:hover]:bg-muted/40">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-0.5">
          <h3 dir="auto" className="truncate font-medium">
            {noteId ? (
              <Link
                href={`/app/notes/${noteId}`}
                className="outline-none after:absolute after:inset-0 after:rounded-xl focus-visible:after:ring-3 focus-visible:after:ring-ring/50"
              >
                {meeting.title}
              </Link>
            ) : (
              meeting.title
            )}
          </h3>
          <span className="text-muted-foreground text-xs tabular-nums">{when}</span>
          {noteId ? (
            <span className="mt-1">
              <RecordingShareBadge recordingId={noteId} />
            </span>
          ) : null}
        </div>
        {noteId ? (
          <ChevronRight
            className="mt-0.5 size-4 shrink-0 text-muted-foreground transition-transform ltr:group-has-[a:hover]:translate-x-0.5 rtl:-scale-x-100 rtl:group-has-[a:hover]:-translate-x-0.5"
            aria-hidden="true"
          />
        ) : null}
      </div>
      {recap ? (
        <p dir="auto" className="line-clamp-2 text-muted-foreground text-sm">
          {recap.summary}
        </p>
      ) : (
        <p className="text-muted-foreground text-sm italic">{t("recap.notReady")}</p>
      )}
      <div className="mt-auto flex flex-wrap items-center justify-between gap-3 text-sm">
        <div className="flex min-w-0 flex-wrap items-center gap-x-4 gap-y-1">
          <MeetingSourceLabel meeting={meeting} />
          {recap && recap.tasks > 0 ? (
            <span className="inline-flex items-center gap-1.5">
              <ListChecks className="size-3.5 text-muted-foreground" aria-hidden="true" />
              {t("recap.tasks", { count: recap.tasks })}
            </span>
          ) : null}
          {recap?.decisions ? (
            <span className="inline-flex items-center gap-1.5">
              <Gavel className="size-3.5 text-muted-foreground" aria-hidden="true" />
              {t("recap.decisions", { count: recap.decisions })}
            </span>
          ) : null}
        </div>
        <MeetingParticipants people={meeting.participants} max={3} />
      </div>
    </article>
  );
}
