"use client";

import type { CalendarController, DatesSetInfo, EventChangeInfo } from "@fullcalendar/react";
import dayGridPlugin from "@fullcalendar/react/daygrid";
import interactionPlugin from "@fullcalendar/react/interaction";
import listPlugin from "@fullcalendar/react/list";
import multiMonthPlugin from "@fullcalendar/react/multimonth";
import timeGridPlugin from "@fullcalendar/react/timegrid";
import { XIcon } from "lucide-react";

import { EventCalendarViews } from "@/components/calendar/event-calendar-views";
import { useDirection } from "@/components/ui/direction";

import type { CalendarEvent } from "../domain/calendar-event";
import { EVENT_ID_ATTRIBUTE } from "./calendar-context-menu";
import { VIEWS } from "./calendar-views";
import { useCalendarLocale } from "./use-calendar-locale";

const plugins = [dayGridPlugin, timeGridPlugin, listPlugin, interactionPlugin, multiMonthPlugin];

type CalendarViewProps = {
  controller: CalendarController;
  events: CalendarEvent[];
  onEventChange: (info: EventChangeInfo) => void;
  onDatesSet: (info: DatesSetInfo) => void;
};

/**
 * FullCalendar in the interface language and direction: in right-to-left languages days run from the right,
 * and the toolbar's previous/next arrows mirror with it. Suspends while a language's locale first loads.
 */
export function CalendarView({ controller, events, onEventChange, onDatesSet }: CalendarViewProps) {
  const locale = useCalendarLocale();
  const direction = useDirection();
  return (
    <EventCalendarViews
      controller={controller}
      initialView={VIEWS[0]}
      plugins={plugins}
      locale={locale}
      direction={direction}
      popoverCloseContent={() => <XIcon className="size-5 text-muted-foreground group-hover:text-foreground" />}
      events={events}
      editable
      eventDidMount={(info) => info.el.setAttribute(EVENT_ID_ATTRIBUTE, info.event.id)}
      eventChange={onEventChange}
      nowIndicator
      datesSet={onDatesSet}
    />
  );
}
