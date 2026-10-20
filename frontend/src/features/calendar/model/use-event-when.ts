"use client";

import { useFormatter } from "use-intl";

/*
 * Исключение из пояса кабинета (src/i18n/time-zone.ts): сетка календаря (FullCalendar, `timeZone: "local"`) и
 * демо-события строятся по локальному времени браузера, поэтому подписи событий печатаются в том же поясе, чтобы
 * не расходиться с сеткой. Календарь перейдёт на пояс кабинета вместе с переходом на свой API.
 */
const viewerTimeZone = () => Intl.DateTimeFormat().resolvedOptions().timeZone;

/** When an event or a slot happens, in the interface language and the viewer's wall clock. */
export function useEventWhen() {
  const format = useFormatter();
  const when = (date: Date, allDay: boolean, width: "short" | "long") =>
    format.dateTime(date, {
      weekday: width,
      month: width,
      day: "numeric",
      ...(allDay ? {} : { hour: "numeric", minute: "2-digit" }),
      timeZone: viewerTimeZone(),
    });

  return {
    /** "Tue, Jun 3" or "Tue, Jun 3, 2:00 PM". */
    short: (date: Date, allDay = false) => when(date, allDay, "short"),
    /** "Tuesday, June 3" or "Tuesday, June 3 at 2:00 PM". */
    long: (date: Date, allDay = false) => when(date, allDay, "long"),
    /** "2:00 PM". */
    time: (date: Date) => format.dateTime(date, { hour: "numeric", minute: "2-digit", timeZone: viewerTimeZone() }),
  };
}

export type EventWhen = ReturnType<typeof useEventWhen>;
