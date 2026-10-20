import { dayIn, daysBetween } from "@/i18n/calendar-days";

/*
 * Календарные дни главной страницы в поясе кабинета `zone` (src/i18n/time-zone.ts). День, найденный здесь, —
 * полночь UTC этого дня: печатать его нужно с `CALENDAR_DAY`, тогда он не сдвинется ни в каком поясе.
 */

export const DAY_MS = 86_400_000;

/** Полночь UTC календарного дня через `days` дней после сегодняшнего (в поясе `zone`). */
export const dayFromToday = (days: number, now: number, zone: string) =>
  new Date(Date.parse(dayIn(now, zone)) + days * DAY_MS);

/** Whole calendar days from the day of `iso` to today in the zone: 0 for today, 1 for yesterday. */
export const daysAgo = (iso: string, now: number, zone: string) => daysBetween(dayIn(iso, zone), dayIn(now, zone));

export type DayPeriod = "morning" | "afternoon" | "evening";

/** The part of the day a greeting names, from the viewer's own hour (0–23). */
export function dayPeriod(hour: number): DayPeriod {
  if (hour >= 5 && hour < 12) return "morning";
  if (hour >= 12 && hour < 18) return "afternoon";
  return "evening";
}
