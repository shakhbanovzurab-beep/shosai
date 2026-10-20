import { cn } from "cn";
import { X } from "lucide-react";
import { useLocale, useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { formatBytes } from "@/i18n/format-units";
import { Link } from "@/lib/navigation";

import type { MeetingCard } from "../domain/library";
import type { NoteFolder } from "../domain/types";
import type { RecordingUpload } from "../model/recording-uploads";
import { CardSummary } from "./card-summary";
import { Duration, FolderBadge, MeetingStart, OpenItems, Participants } from "./note-card";
import { RecordingStatus } from "./recording-status";

// Общая сетка колонок, чтобы строки шли как таблица; второстепенные колонки на узком экране уходят.
export const ROW_GRID =
  "grid grid-cols-[minmax(0,1fr)_auto] items-center gap-4 px-4 py-3 md:grid-cols-[minmax(0,1fr)_8rem_6rem_6rem] xl:grid-cols-[minmax(0,1fr)_8rem_6rem_6rem_8.5rem]";

export function NoteRowsHeader() {
  const t = useTranslations("notes");
  return (
    <div
      className={`${ROW_GRID} border-b py-2 font-medium text-muted-foreground text-xs uppercase tracking-wider`}
      aria-hidden="true"
    >
      <span>{t("fields.meeting")}</span>
      <span className="max-md:hidden">{t("fields.folder")}</span>
      <span className="max-md:hidden">{t("fields.people")}</span>
      <span className="text-end md:text-start">{t("fields.duration")}</span>
      <span className="max-xl:hidden">{t("fields.date")}</span>
    </div>
  );
}

interface NoteRowProps {
  readonly note: MeetingCard;
  readonly folder: NoteFolder | undefined;
}

export function NoteRow({ note, folder }: NoteRowProps) {
  return (
    <article className={`${ROW_GRID} group/note-row relative transition-colors hover:bg-muted/40`}>
      <div className="flex min-w-0 flex-col gap-0.5">
        <h3 className="flex min-w-0 items-center gap-2 font-medium text-sm">
          <Link
            href={`/app/notes/${note.id}`}
            dir="auto"
            className="truncate outline-none after:absolute after:inset-0 focus-visible:after:ring-3 focus-visible:after:ring-ring/50 focus-visible:after:ring-inset"
          >
            {note.title}
          </Link>
          <OpenItems note={note} />
        </h3>
        <CardSummary note={note} className="truncate text-xs" />
      </div>
      <div className="min-w-0 max-md:hidden">
        <FolderBadge folder={folder} />
      </div>
      <div className="max-md:hidden">
        <Participants note={note} />
      </div>
      <div className="justify-self-end md:justify-self-start">
        <Duration minutes={note.durationMinutes} />
      </div>
      <MeetingStart note={note} className="text-muted-foreground text-xs max-xl:hidden" />
    </article>
  );
}

interface RecordingRowProps {
  readonly recording: RecordingUpload;
  readonly onRemove: (id: string) => void;
}

export function RecordingRow({ recording, onRemove }: RecordingRowProps) {
  const t = useTranslations("notes");
  const locale = useLocale();
  return (
    <div className={`${ROW_GRID} bg-muted/20`}>
      <div className="flex min-w-0 items-center gap-2">
        <span
          className={cn(
            "size-1.5 shrink-0 rounded-full",
            recording.failed === null ? "animate-pulse bg-amber-500 motion-reduce:animate-none" : "bg-destructive",
          )}
          aria-hidden="true"
        />
        <span dir="auto" className="truncate font-medium text-sm">
          {recording.name}
        </span>
        <span className="shrink-0 text-muted-foreground text-xs" role="status">
          <RecordingStatus recording={recording} />
        </span>
      </div>
      <span className="max-md:hidden" />
      <span className="max-md:hidden" />
      <div className="flex items-center gap-1 justify-self-end md:justify-self-start">
        <span className="font-mono text-muted-foreground text-xs tabular-nums">
          {formatBytes(locale, recording.size)}
        </span>
        {recording.failed === null ? null : (
          <Button
            variant="ghost"
            size="icon-xs"
            className="text-muted-foreground"
            aria-label={t("remove", { name: recording.name })}
            onClick={() => onRemove(recording.id)}
          >
            <X />
          </Button>
        )}
      </div>
      <span className="max-xl:hidden" />
    </div>
  );
}
