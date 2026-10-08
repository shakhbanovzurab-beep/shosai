import type * as React from "react";

import { cn } from "cn";
import { Gavel, ListChecks, X } from "lucide-react";
import { useFormatter, useLocale, useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { formatBytes } from "@/i18n/format-units";
import { Link } from "@/lib/navigation";

import { formatClock } from "../domain/format";
import type { MeetingNote, NoteFolder, PendingRecording } from "../domain/types";
import { FOLDER_DOT_CLASSES } from "./folder-color-classes";
import { Participants } from "./note-card";

const CHIP_CLASSES =
  "inline-flex items-center gap-1.5 rounded-lg border bg-card px-2.5 py-1 text-foreground/80 text-xs [&_svg]:size-3.5 [&_svg]:text-muted-foreground";

/** The days a group of meetings covers: one day ("Mon, Oct 5"), or the first and last ("Thu, Oct 1 – Fri, Oct 2"). */
function DateSpan({ notes }: { readonly notes: MeetingNote[] }) {
  const format = useFormatter();
  const sorted = notes.map((note) => note.startedAt).toSorted();
  const first = sorted.at(0);
  const last = sorted.at(-1);
  if (!first || !last) return null;
  return format.dateTimeRange(new Date(first), new Date(last), "weekday");
}

interface TimelineDayProps {
  readonly label: string;
  /** Shown under the label; the days the group's notes cover when omitted. */
  readonly dates?: string;
  readonly notes?: MeetingNote[];
  readonly children: React.ReactNode;
}

/**
 * One group of the timeline: its label at the start of the line, its entries on a vertical line after it.
 * The layout is logical, so right to left the line runs down the left with the labels on the right.
 */
export function TimelineDay({ label, dates, notes = [], children }: TimelineDayProps) {
  return (
    <section aria-label={label} className="grid gap-3 sm:grid-cols-[9rem_minmax(0,1fr)] sm:gap-6">
      <div className="sm:pt-0.5">
        <h2 className="font-medium text-[15px]">{label}</h2>
        <p className="text-muted-foreground text-sm">{dates ?? <DateSpan notes={notes} />}</p>
      </div>
      <ol className="flex flex-col border-s">{children}</ol>
    </section>
  );
}

function TimelineDot({ className }: { readonly className: string }) {
  return (
    <span
      className={cn("absolute -start-[6px] top-1.5 size-[11px] rounded-full ring-4 ring-background", className)}
      aria-hidden="true"
    />
  );
}

interface TimelineEntryProps {
  readonly note: MeetingNote;
  readonly folder: NoteFolder | undefined;
}

export function TimelineEntry({ note, folder }: TimelineEntryProps) {
  const t = useTranslations("notes");
  const format = useFormatter();
  const decision = note.decisions.at(0);
  const openTasks = note.actionItems.filter((item) => !item.done).length;

  return (
    <article className="group/entry relative ps-7 pb-8">
      <TimelineDot className={folder ? FOLDER_DOT_CLASSES[folder.color] : "bg-muted-foreground"} />
      <p className="flex flex-wrap items-baseline gap-x-3 font-mono text-muted-foreground text-xs tabular-nums">
        <time dateTime={note.startedAt}>{format.dateTime(new Date(note.startedAt), "time")}</time>
        <span>
          <span className="sr-only">{t("fields.duration")} </span>
          {formatClock(note.durationMinutes * 60)}
        </span>
        <span dir={folder ? "auto" : undefined} className="font-sans">
          {folder?.name ?? t("folders.none")}
        </span>
      </p>
      <h3 className="mt-1.5 mb-1.5 font-medium text-xl leading-snug tracking-tight">
        {/* The link stretches over the entry so the whole block opens the note. */}
        <Link
          href={`/app/notes/${note.id}`}
          dir="auto"
          className="rounded-sm outline-none after:absolute after:inset-0 after:rounded-xl focus-visible:after:ring-3 focus-visible:after:ring-ring/50 group-hover/entry:underline group-hover/entry:underline-offset-4"
        >
          {note.title}
        </Link>
      </h3>
      <p dir="auto" className="mb-3.5 max-w-3xl text-muted-foreground text-sm leading-relaxed">
        {note.summary}
      </p>
      <div className="flex flex-wrap items-center gap-2">
        {decision ? (
          <span className={CHIP_CLASSES}>
            <Gavel aria-hidden="true" />
            <span className="sr-only">{t("timeline.decision")} </span>
            <span dir="auto">{decision}</span>
          </span>
        ) : null}
        {openTasks > 0 ? (
          <span className={CHIP_CLASSES}>
            <ListChecks aria-hidden="true" />
            {t("timeline.openTasks", { count: openTasks })}
          </span>
        ) : null}
        <span className="ms-auto">
          <Participants participants={note.participants} />
        </span>
      </div>
    </article>
  );
}

interface TimelineRecordingProps {
  readonly recording: PendingRecording;
  readonly onRemove: (id: string) => void;
}

/** A just-uploaded file on the timeline, waiting for the transcription service. */
export function TimelineRecording({ recording, onRemove }: TimelineRecordingProps) {
  const t = useTranslations("notes");
  const locale = useLocale();
  return (
    <li className="relative ps-7 pb-8 last:pb-2">
      <span className="absolute -start-[6px] top-1.5 flex size-[11px]" aria-hidden="true">
        <span className="absolute inline-flex size-full animate-ping rounded-full bg-amber-500 opacity-60" />
        <span className="relative inline-flex size-[11px] rounded-full bg-amber-500 ring-4 ring-background" />
      </span>
      <p className="font-mono text-muted-foreground text-xs tabular-nums">{formatBytes(locale, recording.size)}</p>
      <div className="mt-1.5 flex items-center gap-2">
        <h3 dir="auto" className="min-w-0 truncate font-medium text-xl tracking-tight">
          {recording.name}
        </h3>
        <Button
          variant="ghost"
          size="icon-xs"
          className="text-muted-foreground"
          aria-label={t("remove", { name: recording.name })}
          onClick={() => onRemove(recording.id)}
        >
          <X />
        </Button>
      </div>
      <p className="mt-1 text-muted-foreground text-sm" role="status">
        {t("recordings.timelineStatus")}
      </p>
    </li>
  );
}
