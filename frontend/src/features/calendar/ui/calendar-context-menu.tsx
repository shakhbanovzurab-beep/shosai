"use client";

import { type ReactNode, useState } from "react";

import { parseISO } from "date-fns";

import { ContextMenu, ContextMenuContent, ContextMenuTrigger } from "@/components/ui/context-menu";

import type { CalendarEvent, EventSlot } from "../domain/calendar-event";
import type { CalendarActions } from "../model/use-calendar-events";
import { DayMenuItems, EventMenuItems } from "./calendar-menus";

type MenuTarget = { kind: "event"; event: CalendarEvent } | { kind: "slot"; slot: EventSlot };

/** Attribute set on each rendered event (see eventDidMount) so a click can be traced back to it. */
export const EVENT_ID_ATTRIBUTE = "data-event-id";

/**
 * What sits under the pointer: an event, else the day (and, in week and day views, the time slot)
 * FullCalendar marks with `data-date` / `data-time`. Time-grid layers overlap, so every element at
 * the point is checked, not just the topmost.
 */
function resolveTarget(x: number, y: number, find: (id: string) => CalendarEvent | undefined): MenuTarget | null {
  const stack = document.elementsFromPoint(x, y);
  for (const el of stack) {
    const id = el.closest(`[${EVENT_ID_ATTRIBUTE}]`)?.getAttribute(EVENT_ID_ATTRIBUTE);
    const event = id ? find(id) : undefined;
    if (event) return { kind: "event", event };
  }
  const date = stack.map((el) => el.closest("[data-date]")?.getAttribute("data-date")).find(Boolean);
  if (date?.length !== 10) return null;
  const time = stack.map((el) => el.closest("[data-time]")?.getAttribute("data-time")).find(Boolean);
  return { kind: "slot", slot: { date: parseISO(time ? `${date}T${time}` : date), allDay: !time } };
}

type CalendarContextMenuProps = {
  find: (id: string) => CalendarEvent | undefined;
  actions: CalendarActions;
  openDay: (date: Date, view: "timeGridDay" | "timeGridWeek") => void;
  children: ReactNode;
};

/** Right-click an event for its actions, or an empty day or time slot to add one there. */
export function CalendarContextMenu({ find, actions, openDay, children }: CalendarContextMenuProps) {
  const [target, setTarget] = useState<MenuTarget | null>(null);

  const capture = (x: number, y: number) => {
    const next = resolveTarget(x, y, find);
    setTarget(next);
    return next;
  };

  return (
    <ContextMenu>
      <ContextMenuTrigger asChild>
        <div
          onContextMenuCapture={(event) => {
            // Headers and other chrome keep the browser's own menu.
            if (!capture(event.clientX, event.clientY)) event.stopPropagation();
          }}
          onPointerDownCapture={(event) => {
            if (event.pointerType === "touch") capture(event.clientX, event.clientY);
          }}
        >
          {children}
        </div>
      </ContextMenuTrigger>
      <ContextMenuContent className="w-56">
        {target?.kind === "event" ? <EventMenuItems event={target.event} actions={actions} /> : null}
        {target?.kind === "slot" ? <DayMenuItems slot={target.slot} actions={actions} openDay={openDay} /> : null}
      </ContextMenuContent>
    </ContextMenu>
  );
}
