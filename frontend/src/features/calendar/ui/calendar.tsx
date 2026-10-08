"use client";

import { Suspense, useState } from "react";

import { useCalendarController } from "@fullcalendar/react";
import { addHours, differenceInCalendarDays, endOfMonth, startOfHour, startOfMonth } from "date-fns";
import { useFormatter, useTranslations } from "use-intl";

import { NameDialog } from "@/components/name-dialog";
import { Skeleton } from "@/components/ui/skeleton";

import { useCalendarEvents } from "../model/use-calendar-events";
import { CalendarContextMenu } from "./calendar-context-menu";
import { CalendarToolbar } from "./calendar-toolbar";
import { CalendarView } from "./calendar-view";

function CalendarLoading() {
  const t = useTranslations("calendar");
  return (
    <div className="p-4">
      <Skeleton className="h-150 w-full" />
      <span className="sr-only">{t("loading")}</span>
    </div>
  );
}

export function Calendar() {
  const format = useFormatter();
  const controller = useCalendarController();
  const { events, find, actions, nameRequest, closeNameDialog } = useCalendarEvents();
  const [range, setRange] = useState<{ start: Date; end: Date } | null>(null);
  const eventCount = range ? events.filter((event) => event.start >= range.start && event.start < range.end).length : 0;
  // Until FullCalendar reports its period (in its own locale), the current month stands in.
  const [dateInfo, setDateInfo] = useState(() => {
    const now = new Date();
    return {
      title: format.dateTime(now, { month: "long", year: "numeric" }),
      days: differenceInCalendarDays(endOfMonth(now), startOfMonth(now)) + 1,
    };
  });

  return (
    <div className="flex flex-col overflow-hidden rounded-md border">
      <CalendarToolbar
        controller={controller}
        title={dateInfo.title}
        days={dateInfo.days}
        eventCount={eventCount}
        onAdd={() => actions.add({ date: startOfHour(addHours(new Date(), 1)), allDay: false })}
      />

      <CalendarContextMenu
        find={find}
        actions={actions}
        openDay={(date, view) => {
          controller.gotoDate(date);
          controller.changeView(view);
        }}
      >
        <Suspense fallback={<CalendarLoading />}>
          <CalendarView
            controller={controller}
            events={events}
            onEventChange={({ event }) =>
              actions.applyChange(event.id, { start: event.start, end: event.end, allDay: event.allDay })
            }
            onDatesSet={(info) => {
              setDateInfo({
                title: info.view.title,
                days: differenceInCalendarDays(info.view.currentEnd, info.view.currentStart),
              });
              setRange({ start: info.start, end: info.end });
            }}
          />
        </Suspense>
      </CalendarContextMenu>
      <NameDialog request={nameRequest} onClose={closeNameDialog} />
    </div>
  );
}
