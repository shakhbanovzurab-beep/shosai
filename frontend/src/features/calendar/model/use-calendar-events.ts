"use client";

import { useState } from "react";

import { addHours, differenceInCalendarDays, startOfDay } from "date-fns";
import { useTranslations } from "next-intl";
import { toast } from "sonner";

import { demoEvents } from "../data/demo-events";
import { type CalendarEvent, type EventSlot, shiftEvent } from "../domain/calendar-event";
import { useEventWhen } from "./use-event-when";

/** A pending "name this event" prompt; the UI shows it in the shared NameDialog (same shape as its `NameRequest`). */
type EventNameRequest = {
  title: string;
  initial: string;
  submitLabel: string;
  onSubmit: (name: string) => void;
};

/** The calendar's events in client state, with the actions its menus offer. */
export function useCalendarEvents() {
  const t = useTranslations("calendar");
  const common = useTranslations("common");
  const when = useEventWhen();
  const [events, setEvents] = useState<CalendarEvent[]>(() =>
    demoEvents.map((event, index) => ({ ...event, id: `demo-${index}` })),
  );
  const [nameRequest, setNameRequest] = useState<EventNameRequest | null>(null);

  const find = (id: string) => events.find((event) => event.id === id);
  const update = (id: string, patch: (event: CalendarEvent) => Partial<CalendarEvent>) =>
    setEvents((list) => list.map((event) => (event.id === id ? { ...event, ...patch(event) } : event)));

  const actions = {
    rename: (id: string) => {
      const event = find(id);
      if (!event) return;
      setNameRequest({
        title: t("renameTitle"),
        initial: event.title,
        submitLabel: common("actions.rename"),
        onSubmit: (title) => update(id, () => ({ title })),
      });
    },
    reschedule: (id: string, days: number) => update(id, (event) => shiftEvent(event, days)),
    moveToToday: (id: string) =>
      update(id, (event) => shiftEvent(event, differenceInCalendarDays(new Date(), event.start))),
    duplicate: (id: string) => {
      const event = find(id);
      if (!event) return;
      const copy = {
        ...event,
        id: crypto.randomUUID(),
        title: t("copyName", { title: event.title }),
        groupId: undefined,
      };
      setEvents((list) => [...list, copy]);
    },
    copyDetails: (id: string) => {
      const event = find(id);
      if (!event) return;
      const details = t("details", { title: event.title, when: when.short(event.start, event.allDay) });
      navigator.clipboard.writeText(details).then(
        () => toast.success(t("detailsCopied")),
        () => toast.error(t("detailsCopyFailed")),
      );
    },
    remove: (id: string) => {
      const before = events;
      const event = find(id);
      if (!event) return;
      setEvents((list) => list.filter((e) => e.id !== id));
      toast(t("deleted", { title: event.title }), {
        action: { label: common("actions.undo"), onClick: () => setEvents(before) },
      });
    },
    add: ({ date, allDay }: EventSlot) =>
      setNameRequest({
        title: t("newTitle", { when: when.short(date, allDay) }),
        initial: "",
        submitLabel: t("addEvent"),
        onSubmit: (title) =>
          setEvents((list) => [
            ...list,
            allDay
              ? { id: crypto.randomUUID(), title, start: startOfDay(date), allDay: true }
              : { id: crypto.randomUUID(), title, start: date, end: addHours(date, 1) },
          ]),
      }),
    /** Keeps state in step after the event is dragged or resized on the calendar itself. */
    applyChange: (id: string, { start, end, allDay }: { start: Date | null; end: Date | null; allDay: boolean }) => {
      if (start) update(id, () => ({ start, end: end ?? undefined, allDay }));
    },
  };

  return { events, find, actions, nameRequest, closeNameDialog: () => setNameRequest(null) };
}

export type CalendarActions = ReturnType<typeof useCalendarEvents>["actions"];
