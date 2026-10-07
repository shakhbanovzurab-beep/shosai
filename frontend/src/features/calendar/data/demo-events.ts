import { setDate, setHours, setMinutes, startOfMonth } from "date-fns";

import type { CalendarEvent } from "../domain/calendar-event";

/*
 * The demo calendar, laid out around the current month in the viewer's time zone. Event titles are what a
 * user wrote in their own calendar, so they stay as written in every interface language.
 */

const monthStart = startOfMonth(new Date());
const currentYear = new Date().getFullYear();
const d = (day: number) => setDate(monthStart, day);
const dt = (day: number, hour: number, min = 0) => setMinutes(setHours(setDate(monthStart, day), hour), min);

type DemoEvent = Omit<CalendarEvent, "id">;

/** A demo event: its title and start, then whatever else it has. */
const event = (title: string, start: Date, fields: Omit<DemoEvent, "title" | "start"> = {}): DemoEvent => ({
  title,
  start,
  ...fields,
});

export const demoEvents: DemoEvent[] = [
  event("Monthly planning", dt(1, 9, 30), { end: dt(1, 10, 30) }),
  event("Design review", dt(3, 11), { end: dt(3, 12) }),
  event("Client check-in", dt(4, 15), { end: dt(4, 15, 45) }),
  event("Product workshop", d(7), { end: d(9), allDay: true }),
  event("Team standup", dt(9, 10), { groupId: "standup" }),
  event("Finance sync", dt(10, 14, 30), { end: dt(10, 15) }),
  event("Focus block", dt(12, 9), { end: dt(12, 12), display: "background" }),
  event("Sprint planning", dt(15, 9, 30), { end: dt(15, 11) }),
  event("Team standup", dt(16, 10), { groupId: "standup" }),
  event("Ops handoff", dt(18, 16), { end: dt(18, 16, 45) }),
  event("Quarterly report due", d(24), { allDay: true }),
  event("Reset day", d(28), { allDay: true }),
  event("Arham Khan Birthday", new Date(currentYear, 8, 6), { allDay: true }),
];
