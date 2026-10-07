import { useSyncExternalStore } from "react";

import { useFormatter, useTranslations } from "next-intl";

import type { Meeting } from "../domain/meeting";
import { durationMinutes, minutesSinceStart, minutesUntilStart, nearDay } from "../domain/timing";

/*
 * Meeting times are moments on the viewer's own wall clock, as in a calendar, and the domain's day
 * arithmetic runs in the browser's time zone too. next-intl formats in UTC (docs/i18n.md), so these
 * formatters pass the browser's zone. The meeting lists render only after mount (`useNow` is null on the
 * server), so a time is never rendered on the server and then changed by hydration.
 */

let browserZone: string | undefined;
// The zone is read once per page load, so there is nothing to subscribe to.
const unsubscribe = () => undefined;
const subscribe = () => unsubscribe;
const getZone = () => {
  browserZone ??= Intl.DateTimeFormat().resolvedOptions().timeZone;
  return browserZone;
};
// On the server and while hydrating: no zone, so next-intl's UTC applies.
const getServerZone = () => undefined;

/** Meeting days, times and durations in the interface language and the viewer's time zone. */
export function useMeetingTimes() {
  const t = useTranslations("meetings");
  const format = useFormatter();
  const timeZone = useSyncExternalStore<string | undefined>(subscribe, getZone, getServerZone);

  const time = (iso: string) => format.dateTime(new Date(iso), "time", { timeZone });
  const unit = (value: number, name: "hour" | "minute") =>
    format.number(value, { style: "unit", unit: name, unitDisplay: "short" });

  return {
    time,
    /** "Today", "Tomorrow", "Yesterday", otherwise the weekday and date: "Wed, Oct 8". */
    day(day: Date, now: number) {
      const near = nearDay(day, now);
      return near ? t(`day.${near}`) : format.dateTime(day, "short", { weekday: "short", timeZone });
    },
    /** "10:30 – 11:15 AM". */
    range: (meeting: Meeting) =>
      format.dateTimeRange(new Date(meeting.start), new Date(meeting.end), "time", { timeZone }),
    /** "45 min", "1 hr", "1 hr 30 min". */
    duration(meeting: Meeting) {
      const total = durationMinutes(meeting);
      const hours = Math.floor(total / 60);
      const minutes = total % 60;
      if (hours === 0) return unit(minutes, "minute");
      if (minutes === 0) return unit(hours, "hour");
      return format.list([unit(hours, "hour"), unit(minutes, "minute")], { type: "unit", style: "narrow" });
    },
    /** For a meeting in progress: "Started 18 min ago · ends 11:15 AM". */
    live: (meeting: Meeting, now: number) =>
      t("liveSince", { minutes: minutesSinceStart(meeting, now), end: time(meeting.end) }),
    /** For a meeting within the hour: "In 25 min", or "Starting now". */
    startsIn: (meeting: Meeting, now: number) => t("startsIn", { minutes: minutesUntilStart(meeting, now) }),
  };
}
