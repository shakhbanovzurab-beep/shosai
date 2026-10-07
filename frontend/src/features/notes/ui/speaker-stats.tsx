import { useFormatter, useTranslations } from "next-intl";

import { Progress } from "@/components/ui/progress";

import { formatTimestamp } from "../domain/format";
import { speakerStats } from "../domain/speaker-stats";
import type { MeetingNote } from "../domain/types";

/** Who spoke: each speaker's share of the talk time, how long that was and how many lines. */
export function SpeakerStats({ note }: { readonly note: Pick<MeetingNote, "transcript" | "durationMinutes"> }) {
  const t = useTranslations("notesNote");
  const format = useFormatter();
  const stats = speakerStats(note);
  if (stats.length === 0) return null;
  return (
    <section aria-labelledby="speaker-stats-heading" className="flex flex-col gap-4 rounded-xl border bg-card p-4">
      <h3 id="speaker-stats-heading" className="font-medium text-muted-foreground text-sm">
        {t("speakers.title")}
      </h3>
      <ul className="grid gap-x-8 gap-y-4 sm:grid-cols-2">
        {stats.map((stat) => {
          const share = format.number(stat.percent / 100, "percent");
          return (
            <li key={stat.speaker} className="flex flex-col gap-1.5">
              <div className="flex items-baseline justify-between gap-3">
                <span dir="auto" className="truncate font-medium text-sm">
                  {stat.speaker}
                </span>
                <span className="font-medium text-muted-foreground text-sm tabular-nums">{share}</span>
              </div>
              {/* The shared Progress fills from the left; mirrored, it fills from the start of a right-to-left line. */}
              <Progress
                value={stat.percent}
                aria-label={t("speakers.share", { speaker: stat.speaker, share })}
                className="h-1.5"
              />
              <div className="flex justify-between gap-3 text-muted-foreground text-xs tabular-nums">
                <span>{formatTimestamp(stat.seconds)}</span>
                <span>{t("speakers.lines", { count: stat.lines })}</span>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
