import { differenceInCalendarDays } from "date-fns/differenceInCalendarDays";
import { differenceInDays } from "date-fns/differenceInDays";

/* When things happened and are due, as codes and numbers; the UI words and formats them. Days are counted
   in the viewer's own time zone, as the UI shows these dates on their wall clock. */

/** A list date reads relative ("2 hours ago") for the last few days, then as a date. */
export function isRecentMail(date: string, now: Date) {
  return differenceInDays(now, new Date(date)) <= 3;
}

/** When a reply is due, relative to today: late, today, tomorrow, within the week (by weekday), or later. */
export type ReplyDue = "overdue" | "today" | "tomorrow" | "thisWeek" | "later";

export function replyDue(date: string, now: Date): ReplyDue {
  const days = differenceInCalendarDays(new Date(date), now);
  if (days < 0) return "overdue";
  if (days === 0) return "today";
  if (days === 1) return "tomorrow";
  return days < 7 ? "thisWeek" : "later";
}
