import { differenceInDays } from "date-fns/differenceInDays";

import { dayIn, dayOf, daysBetween } from "@/i18n/calendar-days";

/* Когда письмо пришло и к какому сроку ответить — кодами и числами; слова и формат даёт интерфейс. Дни
   считаются в поясе кабинета `zone`, в котором интерфейс и печатает эти даты. */

/** A list date reads relative ("2 hours ago") for the last few days, then as a date. */
export function isRecentMail(date: string, now: Date) {
  return differenceInDays(now, new Date(date)) <= 3;
}

/** When a reply is due, relative to today: late, today, tomorrow, within the week (by weekday), or later. */
export type ReplyDue = "overdue" | "today" | "tomorrow" | "thisWeek" | "later";

export function replyDue(date: string, now: Date, zone: string): ReplyDue {
  const days = daysBetween(dayIn(now, zone), dayOf(date, zone));
  if (days < 0) return "overdue";
  if (days === 0) return "today";
  if (days === 1) return "tomorrow";
  return days < 7 ? "thisWeek" : "later";
}
