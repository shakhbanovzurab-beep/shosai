import { cn } from "cn";
import { Clock, ListChecks } from "lucide-react";
import { useFormatter, useTranslations } from "use-intl";

import { Avatar, AvatarFallback, AvatarGroup, AvatarGroupCount } from "@/components/ui/avatar";
import { Link } from "@/lib/navigation";
import { getInitials } from "@/lib/utils";

import { formatClock } from "../domain/format";
import type { MeetingCard } from "../domain/library";
import type { NoteFolder } from "../domain/types";
import { CardSummary } from "./card-summary";
import { FOLDER_DOT_CLASSES } from "./folder-color-classes";
import { keyed } from "./keyed";

const MAX_AVATARS = 3;

export const CARD_CLASSES =
  "group/note-card relative flex flex-col overflow-hidden rounded-2xl border bg-card text-card-foreground shadow-xs transition-[translate,box-shadow,border-color] duration-200 hover:-translate-y-0.5 hover:border-foreground/15 hover:shadow-lg focus-within:-translate-y-0.5 focus-within:shadow-lg motion-reduce:transition-none motion-reduce:hover:translate-y-0";

/** Вся карточка — одна ссылка: ссылка заголовка растянута на карточку, поэтому это одна остановка клавиатуры. */
export function CardTitleLink({ note, className }: { readonly note: MeetingCard; readonly className?: string }) {
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

/** Кто был на встрече: до трёх аватаров по именам и «+N» за остальных, всего — как считает сервер. */
export function Participants({ note }: { readonly note: Pick<MeetingCard, "participantNames" | "participantCount"> }) {
  const format = useFormatter();
  const names = note.participantNames;
  const extra = note.participantCount - Math.min(names.length, MAX_AVATARS);
  if (note.participantCount === 0) return null;
  return (
    <AvatarGroup aria-label={format.list(names, { type: "unit", style: "short" })}>
      {keyed(names.slice(0, MAX_AVATARS)).map(({ key, value: name }) => (
        <Avatar key={key} size="sm">
          <AvatarFallback className="text-[10px]">{getInitials(name)}</AvatarFallback>
        </Avatar>
      ))}
      {extra > 0 ? (
        <AvatarGroupCount className="text-[10px]">{format.number(extra, { signDisplay: "always" })}</AvatarGroupCount>
      ) : null}
    </AvatarGroup>
  );
}

export function OpenItems({ note }: { readonly note: Pick<MeetingCard, "actionItems"> }) {
  const t = useTranslations("notes");
  const open = note.actionItems;
  if (open === 0) return null;
  return (
    <span className="inline-flex items-center gap-1 text-muted-foreground text-xs">
      <ListChecks className="size-3.5" aria-hidden="true" />
      {t("card.openItems", { count: open })}
    </span>
  );
}

/** Начало встречи, как «5 окт., 9:00», на языке и в часовом поясе кабинета (src/i18n/config.ts). */
export function MeetingStart({
  note,
  className,
}: {
  readonly note: Pick<MeetingCard, "startedAt">;
  readonly className?: string;
}) {
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
  readonly note: MeetingCard;
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
        <CardSummary note={note} className="line-clamp-2" />
      </div>
      <div className="mt-auto flex flex-col gap-4">
        <div className="flex items-center justify-between gap-3">
          <Participants note={note} />
          <div className="flex items-center gap-3">
            <OpenItems note={note} />
            <Duration minutes={note.durationMinutes} />
          </div>
        </div>
      </div>
    </article>
  );
}
