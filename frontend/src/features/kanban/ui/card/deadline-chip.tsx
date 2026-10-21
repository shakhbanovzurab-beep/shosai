"use client";

import { CalendarDays } from "lucide-react";
import { useFormatter, useTranslations } from "use-intl";

import { useToday } from "../../model/board-hooks";
import { Chip } from "./chip";
import { LeoMark } from "./leo-mark";

// Календарные дни — полночь UTC: печатаются в UTC, поэтому не сдвигаются ни в каком поясе.
const DAY = { month: "short", day: "numeric", timeZone: "UTC" } as const;

/** Срок: день или диапазон; просроченный — заметно и словами для чтения с экрана. */
export function DeadlineChip({
  startsOn,
  dueOn,
  done,
  byLeo,
}: {
  startsOn: string | null;
  dueOn: string;
  done: boolean;
  byLeo: boolean;
}) {
  const t = useTranslations("kanban");
  const format = useFormatter();
  const today = useToday();
  const overdue = !done && today !== "" && dueOn < today;
  const due = new Date(dueOn);
  const text = startsOn ? format.dateTimeRange(new Date(startsOn), due, DAY) : format.dateTime(due, DAY);
  return (
    <Chip tone={overdue ? "alert" : "quiet"}>
      <CalendarDays className="size-3 shrink-0" aria-hidden="true" />
      <time dateTime={dueOn} className="truncate tabular-nums">
        {text}
      </time>
      {overdue ? <span className="sr-only">{t("card.overdue")}</span> : null}
      {byLeo ? <LeoMark /> : null}
    </Chip>
  );
}
