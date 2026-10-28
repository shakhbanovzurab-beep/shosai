import { useFormatter, useTranslations } from "use-intl";

import { CALENDAR_DAY, dayOf } from "@/i18n/calendar-days";
import { useTimeZone } from "@/i18n/time-zone";

import type { Meeting } from "../domain/meeting";
import { durationMinutes, minutesSinceStart, minutesUntilStart, nearDay } from "../domain/timing";

/*
 * Время встреч — моменты на часах человека в поясе кабинета (его даёт форматтер); дни считаются в том же поясе.
 */

/** Meeting days, times and durations in the interface language and the cabinet's time zone. */
export function useMeetingTimes() {
  const t = useTranslations("meetings");
  const format = useFormatter();
  const zone = useTimeZone();

  const time = (iso: string) => format.dateTime(new Date(iso), "time");
  const unit = (value: number, name: "hour" | "minute") =>
    format.number(value, { style: "unit", unit: name, unitDisplay: "short" });

  return {
    time,
    /** "Today", "Tomorrow", "Yesterday", otherwise the weekday and date: "Wed, Oct 8"; a day or a moment. */
    day(value: string, now: number) {
      const day = dayOf(value, zone);
      const near = nearDay(day, now, zone);
      return near ? t(`day.${near}`) : format.dateTime(new Date(day), "short", { weekday: "short", ...CALENDAR_DAY });
    },
    /** "10:30 – 11:15 AM". */
    range: (meeting: Meeting) => format.dateTimeRange(new Date(meeting.start), new Date(meeting.end), "time"),
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
    /** Что идёт сейчас: запись — «Recording for 18 min», звонок своей комнаты — «Started 18 min ago», остальное — с концом. */
    ongoing(meeting: Meeting, now: number) {
      if (meeting.recording) return t("recordingSince", { minutes: minutesSinceStart(meeting, now) });
      if (meeting.endless) return t("inCallSince", { minutes: minutesSinceStart(meeting, now) });
      return t("liveSince", { minutes: minutesSinceStart(meeting, now), end: time(meeting.end) });
    },
    /** For a recording in progress, whose end nobody knows yet: "Recording for 18 min". */
    recording: (meeting: Meeting, now: number) => t("recordingSince", { minutes: minutesSinceStart(meeting, now) }),
    /** For a meeting within the hour: "In 25 min", or "Starting now". */
    startsIn: (meeting: Meeting, now: number) => t("startsIn", { minutes: minutesUntilStart(meeting, now) }),
  };
}
