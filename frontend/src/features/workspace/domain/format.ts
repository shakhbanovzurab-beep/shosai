import { differenceInDays, differenceInHours, differenceInMinutes, parseISO } from "date-fns";

import { dayIn, dayOf, daysBetween } from "@/i18n/calendar-days";

/*
 * Даты и суммы числами и кодами; интерфейс называет их на языке человека (`ui/shared/use-dates`). Календарные
 * дни считаются в поясе кабинета `zone` (src/i18n/time-zone.ts): день без времени остаётся собой, у момента берётся
 * его день в этом поясе.
 */

/** Календарных дней от сегодня до дня или момента: 0 — сегодня, −1 — вчера, 1 — завтра. */
export const daysFromToday = (iso: string, now: number, zone: string) =>
  daysBetween(dayIn(now, zone), dayOf(iso, zone));

export const isThisYear = (iso: string, now: number, zone: string) =>
  dayOf(iso, zone).slice(0, 4) === dayIn(now, zone).slice(0, 4);

export type DueTone = "overdue" | "today" | "soon" | "later";

/** How urgent a due day is, and how many calendar days away (negative once it has passed). */
export function dueState(dueOn: string, now: number, zone: string): { days: number; tone: DueTone } {
  const days = daysFromToday(dueOn, now, zone);
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

/** Локальный день клетки выбора даты кодом «2026-10-07»: так хранится срок; клетка — локальная полночь браузера. */
export const dayKey = (now: number) => {
  const date = new Date(now);
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
};
