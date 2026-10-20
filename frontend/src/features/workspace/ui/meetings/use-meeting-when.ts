"use client";

import { useFormatter, useTranslations } from "use-intl";

import { useTimeZone } from "@/i18n/time-zone";

import { daysFromToday, isThisYear } from "../../domain/format";

/** When a meeting happened and how long it ran, in the interface language and the cabinet's time zone. */
export function useMeetingWhen() {
  const t = useTranslations("workspaceMeetings.when");
  const format = useFormatter();
  const zone = useTimeZone();
  const unit = (value: number, name: "hour" | "minute") =>
    format.number(value, { style: "unit", unit: name, unitDisplay: "short" });

  return {
    /** "Today", "Yesterday", "Tomorrow", "Mon, Oct 5", or "Oct 5, 2025" in another year. */
    day(iso: string, now: number) {
      const days = daysFromToday(iso, now, zone);
      if (days === 0) return t("today");
      if (days === -1) return t("yesterday");
      if (days === 1) return t("tomorrow");
      const date = new Date(iso);
      return isThisYear(iso, now, zone)
        ? format.dateTime(date, { weekday: "short", month: "short", day: "numeric" })
        : format.dateTime(date, "medium");
    },
    /** "Nov 1, 2026". */
    date: (iso: string) => format.dateTime(new Date(iso), "medium"),
    /** "09:30" / "9:30 AM", as the language writes the time of day. */
    clock: (iso: string) => format.dateTime(new Date(iso), "time"),
    /** "45 min", "1 hr", "1 hr, 30 min". */
    duration(minutes: number) {
      if (minutes < 60) return unit(minutes, "minute");
      const hours = unit(Math.floor(minutes / 60), "hour");
      const rest = minutes % 60;
      return rest === 0 ? hours : format.list([hours, unit(rest, "minute")], { type: "unit", style: "narrow" });
    },
  };
}
