// Оформление дорожек, списка дней, месяцев, таблиц и служебных элементов.
import type { CalendarOptions } from '@fullcalendar/react'
import { cn } from "cn"
import { xxsTextClass } from './event-calendar-classes'

export const layoutOptions: CalendarOptions = {
    /* Lane
    ----------------------------------------------------------------------------------------- */

    dayLaneClass: (info) => cn(
        'border',
        info.isMajor && 'border-foreground/20',
        info.isDisabled && 'bg-foreground/3',
      ),
    dayLaneInnerClass: (info) => (
        info.isStack
          ? 'm-1'
          : info.isNarrow ? 'mx-px' : 'mx-0.5'
      ),
    slotLaneClass: (info) => cn(
        'border',
        info.isMinor && 'border-dotted',
      ),

    /* List Day
    ----------------------------------------------------------------------------------------- */

    listDayClass: (info) => cn(
        'flex flex-col',
        !info.isLast && 'border-b',
      ),
    listDayHeaderClass: "-mb-px border-b bg-[color-mix(in_oklab,var(--foreground)_3%,var(--background))] flex flex-row items-center justify-between",
    listDayHeaderInnerClass: (info) => cn(
        'm-1.5 px-1.5 py-0.5 rounded-sm text-sm',
        !info.level && 'font-semibold',
        (!info.level && info.isToday)
          ? [
              'bg-chart-1/50',
              info.hasNavLink && 'hover:bg-chart-1/60 focus-visible:outline-3 outline-ring/50',
            ]
          : info.hasNavLink && 'hover:bg-foreground/5',
      ),
    listDayBodyClass: 'mt-px px-1.5 py-2 gap-2',

    /* Single Month (in Multi-Month)
    ----------------------------------------------------------------------------------------- */

    singleMonthClass: (info) => cn(
        info.multiMonthColumns > 1 && 'm-3',
        (info.multiMonthColumns === 1 && !info.isLast) && 'border-b',
      ),
    singleMonthHeaderClass: (info) => cn(
        info.multiMonthColumns > 1 ? 'pb-2' : 'py-1 border-b bg-background',
        'items-center',
      ),
    singleMonthHeaderInnerClass: (info) => cn(
        'px-1.5 py-0.5 rounded-sm text-base font-semibold',
        info.hasNavLink && 'hover:bg-foreground/5',
      ),

    /* Misc Table
    ----------------------------------------------------------------------------------------- */

    tableBodyClass: 'bg-background',
    fillerClass: 'border opacity-50',
    dayNarrowWidth: 100,
    dayHeaderRowClass: 'border',
    dayRowClass: 'border',
    slotHeaderRowClass: 'border',
    slotHeaderInnerClass: 'text-muted-foreground',

    /* Misc Content
    ----------------------------------------------------------------------------------------- */

    navLinkClass: "focus-visible:outline-3 outline-ring/50",
    inlineWeekNumberClass: (info) => cn(
        'absolute start-0 whitespace-nowrap rounded-e-sm text-muted-foreground',
        info.isNarrow
          ? `top-0.5 my-px p-0.5 ${xxsTextClass}`
          : 'top-1 p-1 text-xs',
        info.hasNavLink && 'hover:bg-foreground/5',
      ),
    highlightClass: 'bg-chart-1/20',
    nonBusinessHoursClass: 'bg-foreground/3',
    nowIndicatorLineClass: '-m-px border-1 border-destructive',
    nowIndicatorDotClass: "-m-[6px] border-6 border-destructive size-0 rounded-full ring-2 ring-background",
}
