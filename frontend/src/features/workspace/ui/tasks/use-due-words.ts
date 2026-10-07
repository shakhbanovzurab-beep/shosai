"use client";

import { differenceInCalendarDays, isSameYear, parseISO } from "date-fns";
import { useFormatter, useTranslations } from "next-intl";

import { type DueTone, dueState } from "../../domain/format";

/*
 * Due dates are calendar days ("2026-10-06"). Counting days against today stays in the viewer's own
 * calendar, as the domain does; the day itself is written in UTC, where `new Date("2026-10-06")` is
 * midnight, so it never shifts a day whatever the viewer's time zone.
 */
const UTC = { timeZone: "UTC" } as const;

/** How a due date reads next to a task, in the interface language, and how urgent it looks. */
export function useDueWords() {
  const t = useTranslations("workspaceTasks.due");
  const format = useFormatter();
  const day = (dueOn: string, now: number) =>
    format.dateTime(new Date(dueOn), isSameYear(parseISO(dueOn), now) ? "short" : "medium", UTC);

  return {
    /** "Overdue · Oct 3", "Due today", "Due Fri", "Due Oct 20"; null without a due date. */
    label(dueOn: string | null, now: number): { text: string; tone: DueTone } | null {
      if (!dueOn) return null;
      const { tone } = dueState(dueOn, now);
      const days = differenceInCalendarDays(parseISO(dueOn), now);
      let text = t("on", { date: day(dueOn, now) });
      if (days < 0) text = t("overdue", { date: format.dateTime(new Date(dueOn), "short", UTC) });
      else if (days === 0) text = t("today");
      else if (days === 1) text = t("tomorrow");
      else if (days < 7) text = t("on", { date: format.dateTime(new Date(dueOn), { weekday: "short", ...UTC }) });
      return { text, tone };
    },
    /** "Was due Oct 3", on a task that is done. */
    was: (dueOn: string) => t("was", { date: format.dateTime(new Date(dueOn), "short", UTC) }),
  };
}
