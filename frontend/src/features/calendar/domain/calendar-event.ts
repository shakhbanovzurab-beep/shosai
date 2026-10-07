import { addDays } from "date-fns";

export type CalendarEvent = {
  id: string;
  title: string;
  start: Date;
  end?: Date;
  allDay?: boolean;
  groupId?: string;
  display?: string;
};

/** Where a new event goes: a whole day, or a timed hour starting at `date`. */
export type EventSlot = { date: Date; allDay: boolean };

/** The same event moved by whole days, keeping its length. */
export const shiftEvent = (event: CalendarEvent, days: number): CalendarEvent => ({
  ...event,
  start: addDays(event.start, days),
  end: event.end ? addDays(event.end, days) : undefined,
});
