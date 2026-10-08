// Оформление событий календаря: абстрактные, фоновые, блочные, строчные, колоночные события и ссылки «ещё».
import type { CalendarOptions } from '@fullcalendar/react'
import { cn } from "cn"
import { xxsTextClass, rowPointerResizerClass, columnPointerResizerClass, rowTouchResizerClass, columnTouchResizerClass } from './event-calendar-classes'

export const eventOptions: CalendarOptions = {
    /* Abstract Event
    ----------------------------------------------------------------------------------------- */

    eventShortHeight: 50,
    eventColor: 'var(--primary)',
    eventContrastColor: 'var(--primary-foreground)',
    eventClass: (info) => cn(
        info.isSelected
          ? ['outline-3', info.isDragging && 'shadow-lg']
          : 'focus-visible:outline-3',
        'outline-ring/50',
      ),

    /* Background Event
    ----------------------------------------------------------------------------------------- */

    backgroundEventColor: 'var(--chart-3)',
    backgroundEventClass: 'not-print:bg-[color-mix(in_oklab,var(--fc-event-color)_10%,transparent)] print:border-1 print:border-(--fc-event-color)',
    backgroundEventTitleClass: (info) => cn(
        'opacity-50 italic',
        (info.isNarrow || info.isShort)
          ? `p-1 ${xxsTextClass}`
          : 'p-2 text-xs',
      ),

    /* List-Item Event
    ----------------------------------------------------------------------------------------- */

    listItemEventTimeClass: 'text-muted-foreground',

    /* Block Event
    ----------------------------------------------------------------------------------------- */

    blockEventClass: (info) => cn(
        'group relative border-transparent print:border-(--fc-event-color) bg-(--fc-event-color) print:bg-white hover:bg-[color-mix(in_oklab,var(--fc-event-color)_92%,var(--fc-event-contrast-color))]',
        info.isInteractive && 'active:bg-[color-mix(in_oklab,var(--fc-event-color)_85%,var(--fc-event-contrast-color))]',
        (info.isDragging && !info.isSelected) && 'opacity-75',
      ),
    blockEventInnerClass: 'text-(--fc-event-contrast-color) print:text-black',
    blockEventTimeClass: 'whitespace-nowrap overflow-hidden shrink-1',
    blockEventTitleClass: 'whitespace-nowrap overflow-hidden shrink-100',

    /* Row Event
    ----------------------------------------------------------------------------------------- */

    rowEventClass: (info) => cn(
        'mb-px border-y',
        info.isStart && 'rounded-s-sm border-s',
        info.isEnd && 'rounded-e-sm border-e',
      ),
    rowEventBeforeClass: (info) => cn(
        info.isStartResizable && [
          info.isSelected ? rowTouchResizerClass : rowPointerResizerClass,
          '-start-1',
        ]
      ),
    rowEventAfterClass: (info) => cn(
        info.isEndResizable && [
          info.isSelected ? rowTouchResizerClass : rowPointerResizerClass,
          '-end-1',
        ]
      ),
    rowEventInnerClass: (info) => cn(
        'flex flex-row items-center',
        info.isNarrow ? xxsTextClass : 'text-xs',
      ),
    rowEventTimeClass: (info) => cn(
        info.isNarrow ? 'ps-0.5' : 'ps-1'
      ),
    rowEventTitleClass: (info) => cn(
        info.isNarrow ? 'px-0.5' : 'px-1',
        'font-medium',
      ),

    /* Column Event
    ----------------------------------------------------------------------------------------- */

    columnEventClass: (info) => cn(
        'border-x ring ring-background',
        info.isStart && ['border-t rounded-t-lg', info.isNarrow ? 'mt-px' : 'mt-0.5'],
        info.isEnd && ['border-b rounded-b-lg', info.isNarrow ? 'mb-px' : 'mb-0.5'],
      ),
    columnEventBeforeClass: (info) => cn(
        info.isStartResizable && [
          info.isSelected ? columnTouchResizerClass : columnPointerResizerClass,
          '-top-1',
        ]
      ),
    columnEventAfterClass: (info) => cn(
        info.isEndResizable && [
          info.isSelected ? columnTouchResizerClass : columnPointerResizerClass,
          '-bottom-1',
        ]
      ),
    columnEventInnerClass: (info) => cn(
        'flex',
        info.isShort
          ? 'flex-row items-center gap-1 p-1'
          : ['flex-col', info.isNarrow ? 'px-1 py-0.5' : 'px-2 py-1'],
        (info.isNarrow || info.isShort) ? xxsTextClass : 'text-xs',
      ),
    columnEventTimeClass: (info) => cn(
        !info.isShort && (info.isNarrow ? 'pt-0.5' : 'pt-1')
      ),
    columnEventTitleClass: (info) => cn(
        !info.isShort && (info.isNarrow ? 'py-0.5' : 'py-1'),
        'font-medium',
      ),

    /* More-Link
    ----------------------------------------------------------------------------------------- */

    moreLinkClass: "focus-visible:outline-3 outline-ring/50",
    moreLinkInnerClass: 'whitespace-nowrap overflow-hidden',
    columnMoreLinkClass: "my-0.5 border border-transparent print:border-black rounded-md bg-[color-mix(in_oklab,var(--foreground)_10%,var(--background))] hover:bg-[color-mix(in_oklab,var(--foreground)_13%,var(--background))] print:bg-white ring ring-background",
    columnMoreLinkInnerClass: (info) => cn(
        info.isNarrow
          ? `p-0.5 ${xxsTextClass}`
          : 'p-1 text-xs',
      ),
}
