import type { ReactNode } from "react";

import { cn } from "cn";
import { ArrowRight, X } from "lucide-react";
import { useLocale, useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { formatBytes } from "@/i18n/format-units";

import type { MeetingCard } from "../domain/library";
import { recordingTitle } from "../domain/recordings";
import type { NoteFolder } from "../domain/types";
import type { RecordingUpload } from "../model/recording-uploads";
import { CardSummary, PendingLine } from "./card-summary";
import { keyed } from "./keyed";
import { CARD_CLASSES, CardTitleLink, Duration, FolderBadge, MeetingStart, OpenItems, Participants } from "./note-card";
import { RecordingStatus } from "./recording-status";

/*
 * Слот «последней встречи» в сетке. Загружаемая запись занимает его сразу, а когда она становится встречей, в том же
 * слоте меняется только содержимое: у обеих карточек одни и те же строки каркаса, поэтому высота слота не меняется
 * и сетка под ним не сдвигается (CLS).
 */

const LABEL = "font-medium text-primary text-xs uppercase tracking-wider";

interface FeaturedFrameProps {
  readonly className: string;
  readonly label: ReactNode;
  readonly title: ReactNode;
  readonly status: ReactNode;
  readonly meta: ReactNode;
  readonly aside?: ReactNode;
  readonly corner?: ReactNode;
}

function FeaturedFrame({ className, label, title, status, meta, aside, corner }: FeaturedFrameProps) {
  return (
    <article className={cn(className, "gap-6 p-6")}>
      {corner}
      <div className={cn("grid gap-6", aside ? "md:grid-cols-[1.3fr_1fr]" : null)}>
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-2">{label}</div>
          <h3 className="text-2xl leading-tight tracking-tight">{title}</h3>
          {status}
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 pt-1">{meta}</div>
        </div>
        {aside}
      </div>
    </article>
  );
}

interface FeaturedNoteCardProps {
  readonly note: MeetingCard;
  readonly folder: NoteFolder | undefined;
}

/** Самая новая встреча, крупно наверху библиотеки; ключевые моменты — когда Leo их уже написал. */
export function FeaturedNoteCard({ note, folder }: FeaturedNoteCardProps) {
  const t = useTranslations("notes");
  const points = note.keyPoints.slice(0, 3);
  const aside =
    points.length > 0 ? (
      <div className="flex flex-col gap-3 rounded-xl bg-muted/50 p-4">
        <h4 className="font-medium text-muted-foreground text-xs uppercase tracking-wider">{t("card.keyPoints")}</h4>
        <ul className="flex flex-col gap-2 text-sm">
          {keyed(points).map(({ key, value: point }) => (
            <li key={key} className="flex gap-2">
              <span className="mt-2 size-1 shrink-0 rounded-full bg-foreground/40" aria-hidden="true" />
              <span dir="auto">{point}</span>
            </li>
          ))}
        </ul>
        <span className="mt-auto inline-flex items-center gap-1 font-medium text-sm transition-[gap] group-hover/note-card:gap-2">
          {t("card.openNotes")}
          <ArrowRight className="size-4 rtl:-scale-x-100" aria-hidden="true" />
        </span>
      </div>
    ) : undefined;
  return (
    <FeaturedFrame
      className={CARD_CLASSES}
      label={
        <>
          <span className={LABEL}>{t("card.latest")}</span>
          <FolderBadge folder={folder} />
        </>
      }
      title={<CardTitleLink note={note} />}
      status={<CardSummary note={note} />}
      meta={
        <>
          <Participants note={note} />
          <MeetingStart note={note} className="text-muted-foreground text-xs" />
          <Duration minutes={note.durationMinutes} />
          <OpenItems note={note} />
        </>
      }
      aside={aside}
    />
  );
}

interface FeaturedRecordingCardProps {
  readonly recording: RecordingUpload;
  readonly onRemove: (id: string) => void;
}

/** Запись, которая загружается, в слоте последней встречи: под тем названием, что получит её встреча. */
export function FeaturedRecordingCard({ recording, onRemove }: FeaturedRecordingCardProps) {
  const t = useTranslations("notes");
  const locale = useLocale();
  // Кнопка в углу, а не в строке: при отказе высота карточки не меняется.
  const corner =
    recording.failed === null ? undefined : (
      <Button
        variant="ghost"
        size="icon-xs"
        className="absolute end-4 top-4 text-muted-foreground"
        aria-label={t("remove", { name: recording.name })}
        onClick={() => onRemove(recording.id)}
      >
        <X />
      </Button>
    );
  return (
    <FeaturedFrame
      className="relative flex flex-col overflow-hidden rounded-2xl border border-dashed bg-card/50 text-card-foreground"
      corner={corner}
      label={
        <>
          <span className={LABEL}>{t("recordings.uploading")}</span>
          <FolderBadge folder={undefined} />
        </>
      }
      title={<span dir="auto">{recordingTitle(recording.name)}</span>}
      status={
        recording.failed === null ? (
          <PendingLine>
            <RecordingStatus recording={recording} />
          </PendingLine>
        ) : (
          <p className="text-sm" role="status">
            <RecordingStatus recording={recording} />
          </p>
        )
      }
      meta={
        <span className="font-mono text-muted-foreground text-xs tabular-nums">
          {formatBytes(locale, recording.size)}
        </span>
      }
    />
  );
}
