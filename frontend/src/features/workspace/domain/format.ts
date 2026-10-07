import {
  differenceInCalendarDays,
  differenceInDays,
  differenceInHours,
  differenceInMinutes,
  isSameYear,
  parseISO,
} from "date-fns";

/*
 * Dates and amounts as numbers and codes; the UI words them in the interface language (`ui/shared/use-dates`).
 * Calendar maths runs in the viewer's time zone, as the helpers are called in the browser after mount.
 */

/** Calendar days from today to a day or a moment: 0 today, -1 yesterday, 1 tomorrow. */
export const daysFromToday = (iso: string, now: number) => differenceInCalendarDays(parseISO(iso), now);

export const isThisYear = (iso: string, now: number) => isSameYear(parseISO(iso), now);

export type DueTone = "overdue" | "today" | "soon" | "later";

/** How urgent a due day is, and how many calendar days away (negative once it has passed). */
export function dueState(dueOn: string, now: number): { days: number; tone: DueTone } {
  const days = daysFromToday(dueOn, now);
  if (days < 0) return { days, tone: "overdue" };
  if (days === 0) return { days, tone: "today" };
  return { days, tone: days < 7 ? "soon" : "later" };
}

export type LastActive =
  | { kind: "never" }
  | { kind: "now" }
  | { kind: "hours"; hours: number }
  | { kind: "days"; days: number };

/** When a member was last active: never, just now (15 minutes), hours ago today, or days ago. */
export function lastActive(iso: string | null, now: number): LastActive {
  if (iso === null) return { kind: "never" };
  const at = parseISO(iso);
  if (differenceInMinutes(now, at) < 15) return { kind: "now" };
  const hours = differenceInHours(now, at);
  if (hours < 24) return { kind: "hours", hours: Math.max(1, hours) };
  return { kind: "days", days: differenceInDays(now, at) };
}

/** Inactive this long, a member's seat is worth a second look. */
export const IDLE_DAYS = 30;

export const isIdle = (iso: string | null, now: number) =>
  iso === null || differenceInDays(now, parseISO(iso)) >= IDLE_DAYS;

/** Cents as a currency amount, for `format.number(…, { style: "currency" })`: whole amounts without cents. */
export const moneyAmount = (cents: number) => ({ value: cents / 100, digits: cents % 100 === 0 ? 0 : 2 });

/** The local calendar day of a moment as a code, "2026-10-07": what a due date stores. */
export const dayKey = (now: number) => {
  const date = new Date(now);
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
};
