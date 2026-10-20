import type { ReactNode } from "react";

import { cn } from "cn";
import { useTranslations } from "use-intl";

import type { MeetingCard } from "../domain/library";

type SummaryNote = Pick<MeetingCard, "summary" | "status" | "notes">;

// Пульсирующая точка тихого статуса: записи ещё пишутся, ничего делать не нужно.
const Pulse = () => (
  <span className="relative flex size-1.5" aria-hidden="true">
    <span className="absolute inline-flex size-full animate-ping rounded-full bg-current opacity-60 motion-reduce:animate-none" />
    <span className="relative inline-flex size-1.5 rounded-full bg-current" />
  </span>
);

/**
 * Тихая строка «в работе» с пульсом: идёт встреча, пишутся записи, едет загрузка. Флекс — во внутренней строке:
 * обрезка карточки (line-clamp, truncate) меняет display самого абзаца.
 */
export function PendingLine({ children, className }: { readonly children: ReactNode; readonly className?: string }) {
  return (
    <p className={cn("text-amber-600 text-sm dark:text-amber-400", className)} role="status">
      {/* align-top: строчный флекс по базовой линии добавил бы абзацу место под строкой, и высота бы прыгала. */}
      <span className="inline-flex items-center gap-2 align-top">
        <Pulse />
        {children}
      </span>
    </p>
  );
}

/** Сводка Leo на карточке; пока её нет — тихий статус: идёт встреча, пишутся записи или они не вышли. */
export function CardSummary({ note, className }: { readonly note: SummaryNote; readonly className?: string }) {
  const t = useTranslations("notes");
  if (note.summary)
    return (
      <p dir="auto" className={cn("text-muted-foreground text-sm leading-relaxed", className)}>
        {note.summary}
      </p>
    );
  if (note.status === "active" || note.notes === "processing")
    return (
      <PendingLine className={className}>
        {note.status === "active" ? t("card.live") : t("recordings.transcribingNow")}
      </PendingLine>
    );
  return (
    <p className={cn("text-muted-foreground text-sm", className)}>
      {note.notes === "failed" ? t("card.notesFailed") : t("card.noSummary")}
    </p>
  );
}
