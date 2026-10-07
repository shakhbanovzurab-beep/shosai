import { addDays, differenceInMinutes, isSameDay } from "date-fns";

import type { Meeting } from "./meeting";

/*
 * The minute and day arithmetic behind the meeting times on the page; the UI turns it into words. Days are
 * the viewer's own calendar days (the runtime's time zone): the Meetings page works it out in the browser.
 */

export type NearDay = "today" | "tomorrow" | "yesterday";

/** Whether `day` is today, tomorrow or yesterday as seen from `now`; null for any other day. */
export function nearDay(day: Date, now: number): NearDay | null {
  const today = new Date(now);
  if (isSameDay(day, today)) return "today";
  if (isSameDay(day, addDays(today, 1))) return "tomorrow";
  if (isSameDay(day, addDays(today, -1))) return "yesterday";
  return null;
}

/** How long the meeting is planned to run, in whole minutes. */
export const durationMinutes = (meeting: Meeting) =>
  differenceInMinutes(new Date(meeting.end), new Date(meeting.start));

/** Whole minutes since a meeting in progress started; 0 in its first minute. */
export const minutesSinceStart = (meeting: Meeting, now: number) =>
  Math.max(0, differenceInMinutes(new Date(now), new Date(meeting.start)));

/** Whole minutes until an upcoming meeting starts; 0 when it is about to. */
export const minutesUntilStart = (meeting: Meeting, now: number) =>
  Math.max(0, differenceInMinutes(new Date(meeting.start), new Date(now)));
