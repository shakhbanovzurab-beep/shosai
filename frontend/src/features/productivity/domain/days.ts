/*
 * Calendar days in the demo. Its dates are UTC and next-intl formats in UTC, so a day worked out here is the
 * same day on the server, in the browser and in every time zone (docs/i18n.md).
 */

export const DAY_MS = 86_400_000;

/** UTC midnight of the calendar day `days` after today. */
export const dayFromToday = (days: number, now: number) => new Date((Math.floor(now / DAY_MS) + days) * DAY_MS);

/** Whole calendar days from the day of `iso` to today: 0 for today, 1 for yesterday. */
export const daysAgo = (iso: string, now: number) => Math.floor(now / DAY_MS) - Math.floor(Date.parse(iso) / DAY_MS);

export type DayPeriod = "morning" | "afternoon" | "evening";

/** The part of the day a greeting names, from the viewer's own hour (0–23). */
export function dayPeriod(hour: number): DayPeriod {
  if (hour >= 5 && hour < 12) return "morning";
  if (hour >= 12 && hour < 18) return "afternoon";
  return "evening";
}
