"use client";

import { useSyncExternalStore } from "react";

import { useFormatter, useTranslations } from "next-intl";

import { daysFromToday, dueState, isThisYear, type LastActive } from "../../domain/format";

// The time zone doesn't change while the page is open, so there is nothing to subscribe to.
const noSubscription = () => () => undefined;
const viewerTimeZone = () => Intl.DateTimeFormat().resolvedOptions().timeZone;

/**
 * The viewer's own time zone in the browser; undefined while server rendering, where next-intl formats in
 * UTC. Meeting times and "today" are the viewer's wall clock, so these labels render after mount (the
 * callers wait for `useNow()`, which is null on the server).
 */
const useViewerTimeZone = () => useSyncExternalStore(noSubscription, viewerTimeZone, () => undefined);

/** Dates of the workspace pages in the interface language. */
export function useWorkspaceDates() {
  const t = useTranslations("workspace");
  const format = useFormatter();
  const timeZone = useViewerTimeZone();
  const calendarDay = (day: string, now: number) =>
    // A calendar day ("2026-10-20") is midnight UTC, so it is formatted in UTC, the formatter's own zone.
    isThisYear(day, now) ? format.dateTime(new Date(day), "short") : format.dateTime(new Date(day), "medium");

  return {
    /** "Today", "Yesterday", "Tomorrow", "Mon, Oct 5", or "Oct 5, 2025": the day of a moment on the viewer's clock. */
    day(iso: string, now: number) {
      const days = daysFromToday(iso, now);
      if (days === 0) return t("dates.today");
      if (days === -1) return t("dates.yesterday");
      if (days === 1) return t("dates.tomorrow");
      const date = new Date(iso);
      return isThisYear(iso, now)
        ? format.dateTime(date, { weekday: "short", month: "short", day: "numeric", timeZone })
        : format.dateTime(date, "medium", { timeZone });
    },
    /** "09:30" or "9:30 AM", on the viewer's clock. */
    clock: (iso: string) => format.dateTime(new Date(iso), "time", { timeZone }),
    /** "Target today", "Target Fri", "Overdue · Oct 3": when a project should be done, a calendar day. */
    target(day: string, now: number) {
      const { days } = dueState(day, now);
      if (days < 0) return t("dates.targetOverdue", { date: calendarDay(day, now) });
      if (days === 0) return t("dates.targetToday");
      if (days === 1) return t("dates.targetTomorrow");
      if (days < 7) return t("dates.targetDay", { day: format.dateTime(new Date(day), { weekday: "short" }) });
      return t("dates.targetDate", { date: calendarDay(day, now) });
    },
    /** "today", "yesterday", "5 days ago", then the date: when something was sent or added. */
    ago(iso: string, now: number) {
      const days = -daysFromToday(iso, now);
      if (days < 30) return t("dates.ago", { days: Math.max(0, days) });
      const date = format.dateTime(new Date(iso), isThisYear(iso, now) ? "short" : "medium", { timeZone });
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
