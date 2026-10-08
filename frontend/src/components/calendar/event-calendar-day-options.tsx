// Оформление заголовков и ячеек дней и всплывающего окна дня.
import type { CalendarOptions } from '@fullcalendar/react'
import { cn } from "cn"
import { xxsTextClass } from './event-calendar-classes'

export const dayOptions: CalendarOptions = {
    /* Day Header
    ----------------------------------------------------------------------------------------- */

    dayHeaderClass: (info) => cn(
        'justify-center',
        info.inPopover ? 'border-b bg-foreground/5' :
          info.isMajor && 'border border-foreground/20',
      ),
    dayHeaderInnerClass: (info) => cn(
        'flex flex-row items-center',
        info.isNarrow ? 'text-xs' : 'text-sm',
        info.inPopover ? [
          'm-1.5 px-1 py-0.5 rounded-sm font-semibold',
          info.hasNavLink && 'hover:bg-foreground/5',
        ] : !info.dayNumberText ? [
          'mx-0.5 my-1.5 py-0.5 px-1.5 rounded-sm text-muted-foreground',
          info.hasNavLink && 'hover:bg-foreground/5',
        ] : !info.isToday ? [
          'mx-2 my-2.5 h-6 px-1.5 rounded-sm text-muted-foreground',
          info.hasNavLink && 'hover:bg-foreground/5',
        ] : (
          'group mx-2 my-2 h-7 outline-none'
        )
      ),
    dayHeaderContent: (info) => (
        (info.inPopover || !info.dayNumberText || !info.isToday) ? (
          <>{info.text}</>
        ) : (
          <>
            {info.textParts.map((textPart, i) => (
              <span
                key={i}
                className={cn(
                  'whitespace-pre',
                  (textPart.type === 'day' && info.isToday)
                    ? [
                        'first:-ms-1 last:-me-1 size-7 rounded-full font-semibold flex flex-row items-center justify-center bg-chart-1/50',
                        info.hasNavLink && 'group-hover:bg-chart-1/60 group-focus-visible:outline-3 outline-ring/50',
                      ]
                    : 'text-muted-foreground',
                )}
              >{textPart.value}</span>
            ))}
          </>
        )
      ),

    /* Day Cell
    ----------------------------------------------------------------------------------------- */

    dayCellClass: (info) => cn(
        'border',
        info.isMajor && 'border-foreground/20',
      ),
    dayCellTopClass: (info) => cn(
        info.isNarrow ? 'min-h-0.5' : 'min-h-1',
        'flex flex-row justify-end',
      ),
    dayCellTopInnerClass: (info) => cn(
        'flex flex-row items-center',
        info.isNarrow
          ? `my-px h-5 ${xxsTextClass}`
          : 'my-1 h-6 text-sm',
        !info.isToday
          ? [
              'rounded-s-sm whitespace-nowrap',
              !info.isOther && 'font-semibold',
              info.isNarrow ? 'px-1' : 'px-2',
              !info.monthText && 'text-muted-foreground',
              info.hasNavLink && 'hover:bg-foreground/5',
            ]
          : [
              'group outline-none',
              info.isNarrow
                ? 'mx-px'
                : 'mx-2',
            ]
      ),
    dayCellTopContent: (info) => (
        !info.isToday ? (
          <>{info.text}</>
        ) : (
          <>
            {info.textParts.map((textPart, i) => (
              <span
                key={i}
                className={cn(
                  'whitespace-pre',
                  (textPart.type === 'day' && info.isToday)
                    ? [
                        'rounded-full font-semibold flex flex-row items-center justify-center bg-chart-1/50',
                        info.hasNavLink && 'group-hover:bg-chart-1/60 group-focus-visible:outline-3 outline-ring/50',
                        info.isNarrow
                          ? 'size-5'
                          : 'size-6 first:-ms-1 last:-me-1',
                      ]
                    : (!info.monthText && 'text-muted-foreground'),
                )}
              >{textPart.value}</span>
            ))}
          </>
        )
      ),
    dayCellInnerClass: (info) => cn(info.inPopover && 'p-2'),

    /* Popover
    ----------------------------------------------------------------------------------------- */

    popoverClass: 'border rounded-md overflow-hidden shadow-lg m-1 bg-popover text-popover-foreground min-w-55',
    popoverCloseClass: "group absolute top-1.5 end-1.5 p-0.5 rounded-sm hover:bg-foreground/5 focus-visible:outline-3 outline-ring/50",
}
