// Оформление по видам календаря поверх пользовательских настроек видов.
import type { CalendarOptions } from '@fullcalendar/react'
import { cn } from "cn"
import { xxsTextClass, tallDayCellBottomClass, getShortDayCellBottomClass, dayRowCommonClasses } from './event-calendar-classes'

export function viewOptions(userViews: CalendarOptions['views']): CalendarOptions['views'] {
  return {
    ...userViews,
    dayGrid: {
      ...dayRowCommonClasses,
      tableHeaderClass: 'bg-background',
      dayHeaderAlign: (info) => info.inPopover ? 'start' : info.isNarrow ? 'center' : 'end',
      dayHeaderDividerClass: 'border-b',
      dayCellBottomClass: getShortDayCellBottomClass,
      ...userViews?.dayGrid,
    },
    multiMonth: {
      ...dayRowCommonClasses,
      className: 'bg-foreground/3',
      tableHeaderClass: (info) => cn(info.multiMonthColumns === 1 && 'bg-background'),
      dayHeaderAlign: (info) => info.inPopover ? 'start' : info.isNarrow ? 'center' : 'end',
      dayHeaderDividerClass: (info) => cn(info.multiMonthColumns === 1 && 'border-b'),
      dayCellBottomClass: getShortDayCellBottomClass,
      tableBodyClass: (info) => cn(info.multiMonthColumns > 1 && 'border rounded-sm overflow-hidden'),
      ...userViews?.multiMonth,
    },
    timeGrid: {
      ...dayRowCommonClasses,
      tableHeaderClass: 'bg-background',
      dayHeaderAlign: (info) => info.inPopover ? 'start' : 'center',
      dayHeaderDividerClass: (info) => cn(
        'border-b',
        !info.options.allDaySlot && 'border-foreground/20 not-print:shadow-sm',
      ),
      dayCellBottomClass: tallDayCellBottomClass,

      /* TimeGrid > Week Number Header
      ------------------------------------------------------------------------------------- */

      weekNumberHeaderClass: 'items-center justify-end',
      weekNumberHeaderInnerClass: (info) => cn(
        'mx-0.5 h-6 px-1.5 text-muted-foreground flex flex-row items-center rounded-sm',
        info.isNarrow ? 'text-xs' : 'text-sm',
        info.hasNavLink && 'hover:bg-foreground/5',
      ),

      /* TimeGrid > All-Day Header
      ------------------------------------------------------------------------------------- */

      allDayHeaderClass: 'items-center',
      allDayHeaderInnerClass: (info) => cn(
        'm-2 text-muted-foreground',
        info.isNarrow ? xxsTextClass : 'text-xs',
      ),
      allDayDividerClass: 'border-b border-foreground/20 not-print:shadow-sm',

      /* TimeGrid > Slot Header
      ------------------------------------------------------------------------------------- */

      slotHeaderClass: 'justify-end',
      slotHeaderInnerClass: (info) => cn(
        'relative m-2',
        info.isNarrow
          ? `-top-3.5 ${xxsTextClass}`
          : '-top-4 text-xs',
        info.isFirst && 'hidden',
      ),
      slotHeaderDividerClass: 'border-e',

      ...userViews?.timeGrid,
    },
    list: {

      /* List-View > List-Item Event
      ------------------------------------------------------------------------------------- */

      listItemEventClass: (info) => cn(
        'group py-1 rounded-sm hover:bg-muted/50',
        info.isInteractive && 'focus-visible:bg-muted/50 -outline-offset-3',
      ),
      listItemEventBeforeClass: 'w-1.5 bg-(--fc-event-color) rounded-full',
      listItemEventInnerClass: '[display:contents]',
      listItemEventTimeClass: "-order-1 shrink-0 w-1/2 max-w-60 px-4 py-2 whitespace-nowrap overflow-hidden text-ellipsis text-sm",
      listItemEventTitleClass: (info) => cn(
        'grow min-w-0 px-4 py-2 whitespace-nowrap overflow-hidden text-sm',
        info.event.url && 'group-hover:underline',
      ),

      /* No-Events Screen
      ------------------------------------------------------------------------------------- */

      noEventsClass: 'grow flex flex-col items-center justify-center',
      noEventsInnerClass: 'py-15 text-muted-foreground',

      ...userViews?.list,
    },
  }
}
