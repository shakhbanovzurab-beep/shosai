import { cn } from "cn";
import { ArrowRight, Clock, ListChecks } from "lucide-react";
import { useFormatter, useTranslations } from "use-intl";

import { Avatar, AvatarFallback, AvatarGroup, AvatarGroupCount } from "@/components/ui/avatar";
import { Link } from "@/lib/navigation";
import { getInitials } from "@/lib/utils";

import { formatClock } from "../domain/format";
import type { MeetingNote, NoteFolder, NoteParticipant } from "../domain/types";
import { FOLDER_DOT_CLASSES } from "./folder-color-classes";

const MAX_AVATARS = 3;

const CARD_CLASSES =
  "group/note-card relative flex flex-col overflow-hidden rounded-2xl border bg-card text-card-foreground shadow-xs transition-[translate,box-shadow,border-color] duration-200 hover:-translate-y-0.5 hover:border-foreground/15 hover:shadow-lg focus-within:-translate-y-0.5 focus-within:shadow-lg motion-reduce:transition-none motion-reduce:hover:translate-y-0";

/** The whole card is one link: the title's link stretches over the card, so it is a single keyboard stop. */
function CardTitleLink({ note, className }: { readonly note: MeetingNote; readonly className?: string }) {
  return (
    <Link
      href={`/app/notes/${note.id}`}
      dir="auto"
      className={cn(
        "outline-none after:absolute after:inset-0 after:rounded-2xl focus-visible:after:ring-3 focus-visible:after:ring-ring/50",
        className,
      )}
    >
      {note.title}
    </Link>
  );
}

export function FolderBadge({ folder }: { readonly folder: NoteFolder | undefined }) {
  const t = useTranslations("notes");
  if (!folder) return <span className="text-muted-foreground text-xs">{t("folders.none")}</span>;
  return (
    <span className="inline-flex min-w-0 items-center gap-1.5 rounded-full bg-muted px-2 py-0.5 font-medium text-xs">
      <span className={cn("size-1.5 shrink-0 rounded-full", FOLDER_DOT_CLASSES[folder.color])} aria-hidden="true" />
      <span dir="auto" className="truncate">
        {folder.name}
      </span>
    </span>
  );
}

export function Participants({ participants }: { readonly participants: NoteParticipant[] }) {
  const format = useFormatter();
  const extra = participants.length - MAX_AVATARS;
  return (
    <AvatarGroup
      aria-label={format.list(
        participants.map((p) => p.name),
        { type: "unit", style: "short" },
      )}
    >
      {participants.slice(0, MAX_AVATARS).map((participant) => (
        <Avatar key={participant.name} size="sm">
          <AvatarFallback className="text-[10px]">{getInitials(participant.name)}</AvatarFallback>
        </Avatar>
      ))}
      {extra > 0 ? (
        <AvatarGroupCount className="text-[10px]">{format.number(extra, { signDisplay: "always" })}</AvatarGroupCount>
      ) : null}
    </AvatarGroup>
  );
}

export function OpenItems({ note }: { readonly note: MeetingNote }) {
  const t = useTranslations("notes");
  const open = note.actionItems.filter((item) => !item.done).length;
  if (open === 0) return null;
  return (
    <span className="inline-flex items-center gap-1 text-muted-foreground text-xs">
      <ListChecks className="size-3.5" aria-hidden="true" />
      {t("card.openItems", { count: open })}
    </span>
  );
}

/** When the meeting started, as "Oct 5, 9:00 AM" in the interface language (UTC, like the demo data). */
export function MeetingStart({ note, className }: { readonly note: MeetingNote; readonly className?: string }) {
  const format = useFormatter();
  return (
    <time className={className} dateTime={note.startedAt}>
      {format.dateTime(new Date(note.startedAt), "shortDateTime")}
    </time>
  );
}

export function Duration({ minutes }: { readonly minutes: number }) {
  const t = useTranslations("notes");
  return (
    <span className="inline-flex items-center gap-1 font-mono text-muted-foreground text-xs tabular-nums">
      <Clock className="size-3.5" aria-hidden="true" />
      <span className="sr-only">{t("fields.duration")} </span>
      {formatClock(minutes * 60)}
    </span>
  );
}

interface NoteCardProps {
  readonly note: MeetingNote;
  readonly folder: NoteFolder | undefined;
}

export function NoteCard({ note, folder }: NoteCardProps) {
  return (
    <article className={cn(CARD_CLASSES, "gap-4 p-5")}>
      <div className="flex items-center justify-between gap-3">
        <FolderBadge folder={folder} />
        <MeetingStart note={note} className="shrink-0 text-muted-foreground text-xs" />
      </div>
      <div className="flex flex-col gap-1.5">
        <h3 className="font-medium text-base leading-snug">
          <CardTitleLink note={note} />
        </h3>
        <p dir="auto" className="line-clamp-2 text-muted-foreground text-sm leading-relaxed">
          {note.summary}
        </p>
      </div>
      <div className="mt-auto flex flex-col gap-4">
        <div className="flex items-center justify-between gap-3">
          <Participants participants={note.participants} />
          <div className="flex items-center gap-3">
            <OpenItems note={note} />
            <Duration minutes={note.durationMinutes} />
          </div>
        </div>
      </div>
    </article>
  );
}

/** The newest meeting, shown large at the top of the library. */
export function FeaturedNoteCard({ note, folder }: NoteCardProps) {
  const t = useTranslations("notes");
  return (
    <article className={cn(CARD_CLASSES, "gap-6 p-6")}>
      <div className="grid gap-6 md:grid-cols-[1.3fr_1fr]">
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium text-primary text-xs uppercase tracking-wider">{t("card.latest")}</span>
            <FolderBadge folder={folder} />
          </div>
          <h3 className="text-2xl leading-tight tracking-tight">
            <CardTitleLink note={note} />
          </h3>
          <p dir="auto" className="text-muted-foreground text-sm leading-relaxed">
            {note.summary}
          </p>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 pt-1">
            <Participants participants={note.participants} />
            <MeetingStart note={note} className="text-muted-foreground text-xs" />
            <Duration minutes={note.durationMinutes} />
            <OpenItems note={note} />
          </div>
        </div>
        <div className="flex flex-col gap-3 rounded-xl bg-muted/50 p-4">
          <h4 className="font-medium text-muted-foreground text-xs uppercase tracking-wider">{t("card.keyPoints")}</h4>
          <ul className="flex flex-col gap-2 text-sm">
            {note.keyPoints.slice(0, 3).map((point) => (
              <li key={point} className="flex gap-2">
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
      </div>
    </article>
  );
}
