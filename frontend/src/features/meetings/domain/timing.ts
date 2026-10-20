import { differenceInMinutes } from "date-fns";

import { dayIn, daysBetween } from "@/i18n/calendar-days";

import type { Meeting } from "./meeting";

/*
 * Минуты и дни за временем встреч на странице; слова им даёт интерфейс. Дни — календарные дни пояса кабинета
 * (src/i18n/time-zone.ts): день — строка «2026-10-20».
 */

export type NearDay = "today" | "tomorrow" | "yesterday";

/** Is `day` today, tomorrow or yesterday as seen from `now` in the zone; null for any other day. */
export function nearDay(day: string, now: number, zone: string): NearDay | null {
  const days = daysBetween(dayIn(now, zone), day);
  if (days === 0) return "today";
  if (days === 1) return "tomorrow";
  if (days === -1) return "yesterday";
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
