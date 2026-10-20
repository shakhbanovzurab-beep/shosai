"use client";

import { useFormatter, useTranslations } from "use-intl";

import { CALENDAR_DAY } from "@/i18n/calendar-days";
import { useTimeZone } from "@/i18n/time-zone";

import { type DueTone, dueState, isThisYear } from "../../domain/format";

/*
 * Срок — календарный день («2026-10-06»). Дни до него считаются от сегодня в поясе кабинета, как в домене, а сам
 * день печатается в UTC, где `new Date("2026-10-06")` — полночь, поэтому он не сдвигается ни в каком поясе.
 */

/** How a due date reads next to a task, in the interface language, and how urgent it looks. */
export function useDueWords() {
  const t = useTranslations("workspaceTasks.due");
  const format = useFormatter();
  const zone = useTimeZone();
  const day = (dueOn: string, now: number) =>
    format.dateTime(new Date(dueOn), isThisYear(dueOn, now, zone) ? "short" : "medium", CALENDAR_DAY);

  return {
    /** "Overdue · Oct 3", "Due today", "Due Fri", "Due Oct 20"; null without a due date. */
    label(dueOn: string | null, now: number): { text: string; tone: DueTone } | null {
      if (!dueOn) return null;
      const { days, tone } = dueState(dueOn, now, zone);
      let text = t("on", { date: day(dueOn, now) });
      if (days < 0) text = t("overdue", { date: format.dateTime(new Date(dueOn), "short", CALENDAR_DAY) });
      else if (days === 0) text = t("today");
      else if (days === 1) text = t("tomorrow");
      else if (days < 7)
        text = t("on", { date: format.dateTime(new Date(dueOn), { weekday: "short", ...CALENDAR_DAY }) });
      return { text, tone };
    },
    /** "Was due Oct 3", on a task that is done. */
    was: (dueOn: string) => t("was", { date: format.dateTime(new Date(dueOn), "short", CALENDAR_DAY) }),
  };
}
