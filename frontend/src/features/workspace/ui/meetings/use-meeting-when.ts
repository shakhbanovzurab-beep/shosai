"use client";

import { differenceInCalendarDays, isSameYear, parseISO } from "date-fns";
import { useFormatter, useTranslations } from "use-intl";

/*
 * A meeting's start reads in the viewer's own wall clock, as it always has. Every caller renders these
 * only in the browser after mount (once `useNow()` is set, or in a dialog the user opened), so the
 * viewer's time zone never meets the server render (next-intl formats in UTC by default).
 */
const viewerTimeZone = () => Intl.DateTimeFormat().resolvedOptions().timeZone;

/** When a meeting happened and how long it ran, in the interface language. */
export function useMeetingWhen() {
  const t = useTranslations("workspaceMeetings.when");
  const format = useFormatter();
  const unit = (value: number, name: "hour" | "minute") =>
    format.number(value, { style: "unit", unit: name, unitDisplay: "short" });

  return {
    /** "Today", "Yesterday", "Tomorrow", "Mon, Oct 5", or "Oct 5, 2025" in another year. */
    day(iso: string, now: number) {
      const date = parseISO(iso);
      const days = differenceInCalendarDays(date, now);
      if (days === 0) return t("today");
      if (days === -1) return t("yesterday");
      if (days === 1) return t("tomorrow");
      const timeZone = viewerTimeZone();
      return isSameYear(date, now)
        ? format.dateTime(date, { weekday: "short", month: "short", day: "numeric", timeZone })
        : format.dateTime(date, "medium", { timeZone });
    },
    /** "Nov 1, 2026". */
    date: (iso: string) => format.dateTime(parseISO(iso), "medium", { timeZone: viewerTimeZone() }),
    /** "09:30" / "9:30 AM", as the language writes the time of day. */
    clock: (iso: string) => format.dateTime(parseISO(iso), "time", { timeZone: viewerTimeZone() }),
    /** "45 min", "1 hr", "1 hr, 30 min". */
    duration(minutes: number) {
      if (minutes < 60) return unit(minutes, "minute");
      const hours = unit(Math.floor(minutes / 60), "hour");
      const rest = minutes % 60;
      return rest === 0 ? hours : format.list([hours, unit(rest, "minute")], { type: "unit", style: "narrow" });
    },
  };
}
