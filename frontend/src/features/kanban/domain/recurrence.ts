import { type Recurrence, WEEKDAYS, type Weekday } from "./tasks-contract";

/*
 * Расписание повторяющейся задачи (KG-D5, решение владельца): следующая задача появляется, когда текущую
 * закрыли, и её срок — следующая дата расписания после исходного срока, но не раньше сегодняшнего дня
 * человека. Дни — календарные строки "2026-10-21", считаются в UTC, поэтому не зависят от пояса браузера.
 */

const DAY_MS = 86_400_000;

const toTime = (day: string) => Date.parse(`${day}T00:00:00Z`);
const toDay = (time: number) => new Date(time).toISOString().slice(0, 10);

export const addDays = (day: string, days: number) => toDay(toTime(day) + days * DAY_MS);
export const daysFrom = (from: string, to: string) => Math.round((toTime(to) - toTime(from)) / DAY_MS);
const laterOf = (a: string, b: string) => (a > b ? a : b);

/** День недели дня в порядке `WEEKDAYS` (понедельник — первый). */
export const weekdayOf = (day: string): Weekday => WEEKDAYS[(new Date(toTime(day)).getUTCDay() + 6) % 7];

const daysInMonth = (year: number, month: number) => new Date(Date.UTC(year, month + 1, 0)).getUTCDate();

/** День месяца `day` в этом месяце: 29–31 падают на последний день короткого месяца. */
function monthlyIn(year: number, month: number, day: number) {
  return toDay(Date.UTC(year, month, Math.min(day, daysInMonth(year, month))));
}

/** Первая дата расписания в `from` или позже. */
export function occurrenceFrom(rule: Recurrence, from: string): string {
  if (rule.every === "day") return from;
  if (rule.every === "week") {
    const chosen = new Set(rule.weekdays);
    for (let shift = 0; shift < 7; shift++) {
      const day = addDays(from, shift);
      if (chosen.has(weekdayOf(day))) return day;
    }
    return from;
  }
  const start = new Date(toTime(from));
  const year = start.getUTCFullYear();
  const month = start.getUTCMonth();
  const here = monthlyIn(year, month, rule.day);
  return here >= from ? here : monthlyIn(month === 11 ? year + 1 : year, (month + 1) % 12, rule.day);
}

/** Срок следующей задачи: первая дата после исходного срока, не раньше `today`. */
export const nextDue = (rule: Recurrence, dueOn: string, today: string) =>
  occurrenceFrom(rule, laterOf(addDays(dueOn, 1), today));

/** Срок, который получает задача без срока, когда ей задают повтор: первая дата с сегодняшнего дня. */
export const firstDue = (rule: Recurrence, today: string) => occurrenceFrom(rule, today);

/** Начало диапазона следующей задачи: диапазон сохраняет длину. */
export function shiftedStart(startsOn: string | null, dueOn: string, nextDueOn: string): string | null {
  return startsOn === null ? null : addDays(startsOn, daysFrom(dueOn, nextDueOn));
}

/**
 * Правило, когда человек выбирает вид повтора: прежнее правило того же вида сохраняется, новое берёт день недели
 * или день месяца от `anchor` — срока задачи или сегодняшнего дня; без него — понедельник и первое число.
 */
export function recurrenceFor(
  every: Recurrence["every"] | "never",
  previous: Recurrence | null,
  anchor: string | null,
): Recurrence | null {
  if (every === "never") return null;
  if (every === "day") return { every: "day" };
  if (every === "week")
    return previous?.every === "week" ? previous : { every: "week", weekdays: [anchor ? weekdayOf(anchor) : "mon"] };
  return previous?.every === "month" ? previous : { every: "month", day: anchor ? Number(anchor.slice(8, 10)) : 1 };
}

/** Дни недели от первого дня недели в языке человека (`firstDay` из Intl: 1 — понедельник … 7 — воскресенье). */
export const weekdaysFrom = (firstDay: number): Weekday[] => [
  ...WEEKDAYS.slice(firstDay - 1),
  ...WEEKDAYS.slice(0, firstDay - 1),
];

/** Правило осмысленно: неделя с хотя бы одним днём без повторов, месяц с днём 1–31. */
export function isValidRecurrence(rule: Recurrence): boolean {
  if (rule.every === "week")
    return (
      rule.weekdays.length > 0 && rule.weekdays.length <= 7 && new Set(rule.weekdays).size === rule.weekdays.length
    );
  if (rule.every === "month") return Number.isInteger(rule.day) && rule.day >= 1 && rule.day <= 31;
  return true;
}
