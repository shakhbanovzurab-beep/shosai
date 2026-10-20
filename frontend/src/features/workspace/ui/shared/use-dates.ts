"use client";

import { useFormatter, useTranslations } from "use-intl";

import { CALENDAR_DAY } from "@/i18n/calendar-days";
import { useTimeZone } from "@/i18n/time-zone";

import { daysFromToday, dueState, isThisYear, type LastActive } from "../../domain/format";

/**
 * Даты страниц рабочего пространства на языке интерфейса. Моменты печатаются в поясе кабинета (его даёт
 * форматтер), «сегодня» и «вчера» считаются в нём же, а календарный день без времени — в UTC (`CALENDAR_DAY`).
 */
export function useWorkspaceDates() {
  const t = useTranslations("workspace");
  const format = useFormatter();
  const zone = useTimeZone();
  const calendarDay = (day: string, now: number) =>
    format.dateTime(new Date(day), isThisYear(day, now, zone) ? "short" : "medium", CALENDAR_DAY);

  return {
    /** "Today", "Yesterday", "Tomorrow", "Mon, Oct 5", or "Oct 5, 2025": the day of a moment on the person's clock. */
    day(iso: string, now: number) {
      const days = daysFromToday(iso, now, zone);
      if (days === 0) return t("dates.today");
      if (days === -1) return t("dates.yesterday");
      if (days === 1) return t("dates.tomorrow");
      const date = new Date(iso);
      return isThisYear(iso, now, zone)
        ? format.dateTime(date, { weekday: "short", month: "short", day: "numeric" })
        : format.dateTime(date, "medium");
    },
    /** "09:30" or "9:30 AM", on the person's clock. */
    clock: (iso: string) => format.dateTime(new Date(iso), "time"),
    /** "Target today", "Target Fri", "Overdue · Oct 3": when a project should be done, a calendar day. */
    target(day: string, now: number) {
      const { days } = dueState(day, now, zone);
      if (days < 0) return t("dates.targetOverdue", { date: calendarDay(day, now) });
      if (days === 0) return t("dates.targetToday");
      if (days === 1) return t("dates.targetTomorrow");
      if (days < 7)
        return t("dates.targetDay", { day: format.dateTime(new Date(day), { weekday: "short", ...CALENDAR_DAY }) });
      return t("dates.targetDate", { date: calendarDay(day, now) });
    },
    /** "today", "yesterday", "5 days ago", then the date: when something was sent or added. */
    ago(iso: string, now: number) {
      const days = -daysFromToday(iso, now, zone);
      if (days < 30) return t("dates.ago", { days: Math.max(0, days) });
      const date = format.dateTime(new Date(iso), isThisYear(iso, now, zone) ? "short" : "medium");
      return t("dates.on", { date });
    },
    /** "Active now", "2 hours ago", "Yesterday", "12 days ago", "Never signed in". */
    lastActive(active: LastActive) {
      if (active.kind === "never") return t("dates.neverSignedIn");
      if (active.kind === "now") return t("dates.activeNow");
      if (active.kind === "hours") return t("dates.hoursAgo", { count: active.hours });
      return t("dates.daysAgo", { count: active.days });
    },
  };
}
