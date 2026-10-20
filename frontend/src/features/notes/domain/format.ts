import { dayIn, daysBetween } from "@/i18n/calendar-days";

/*
 * Formatting that isn't a date: dates are formatted where they are shown, in the interface language
 * (`useFormatter` with the named formats of src/i18n/formats.ts, в поясе кабинета).
 */

const unitFormats = new Map<string, Intl.NumberFormat>();

function unitFormat(locale: string, unit: "hour" | "minute") {
  const key = `${locale}|${unit}`;
  let format = unitFormats.get(key);
  if (!format) {
    format = new Intl.NumberFormat(locale, { style: "unit", unit, unitDisplay: "short" });
    unitFormats.set(key, format);
  }
  return format;
}

/** How long a meeting ran, in the interface language: "48 min", "1 hr 5 min", "1 ч 5 мин", "1 時間 5 分". */
export function formatMeetingDuration(locale: string, minutes: number) {
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (hours === 0) return unitFormat(locale, "minute").format(minutes);
  const parts = [unitFormat(locale, "hour").format(hours)];
  if (rest > 0) parts.push(unitFormat(locale, "minute").format(rest));
  return new Intl.ListFormat(locale, { type: "unit", style: "narrow" }).format(parts);
}

/** 95 → «1:35»: момент записи, как его пишут плееры на любом языке; доли секунды округляются. */
export function formatTimestamp(seconds: number) {
  const whole = Math.round(seconds);
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
}

/** 24 → "00:24:00", a running time in the same media-player style. */
export function formatClock(totalSeconds: number) {
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = Math.floor(totalSeconds % 60);
  return [hours, minutes, seconds].map((part) => String(part).padStart(2, "0")).join(":");
}

/** The headings of the library, newest first; the UI names them in the interface language. */
export const RECENCY_GROUPS = ["today", "yesterday", "thisWeek", "earlier"] as const;
export type RecencyGroup = (typeof RECENCY_GROUPS)[number];

/** Под каким заголовком встреча: календарные дни считаются в поясе кабинета `zone`. */
export function getRecencyGroup(iso: string, now: Date, zone: string): RecencyGroup {
  const daysAgo = daysBetween(dayIn(iso, zone), dayIn(now, zone));
  if (daysAgo <= 0) return "today";
  if (daysAgo === 1) return "yesterday";
  if (daysAgo < 7) return "thisWeek";
  return "earlier";
}

/** Newest first, bucketed into today, yesterday, this week and earlier. */
export function groupNotesByRecency<T extends { startedAt: string }>(
  notes: readonly T[],
  zone: string,
  now = new Date(),
): { recency: RecencyGroup; items: T[] }[] {
  const groups = new Map<RecencyGroup, T[]>();
  for (const note of notes.toSorted((a, b) => b.startedAt.localeCompare(a.startedAt))) {
    const group = getRecencyGroup(note.startedAt, now, zone);
    groups.set(group, [...(groups.get(group) ?? []), note]);
  }
  return Array.from(groups, ([recency, items]) => ({ recency, items }));
}
