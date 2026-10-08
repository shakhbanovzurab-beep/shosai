import type { CalendarOptions, DayCellInfo } from '@fullcalendar/react'
import { cn } from "cn"


export const xxsTextClass = 'text-[0.6875rem]/[1.090909]'

export const blockPointerResizerClass = 'absolute hidden group-hover:block'
export const rowPointerResizerClass = `${blockPointerResizerClass} inset-y-0 w-2`
export const columnPointerResizerClass = `${blockPointerResizerClass} inset-x-0 h-2`

export const blockTouchResizerClass = 'absolute size-2 border border-(--fc-event-color) bg-background rounded-full'
export const rowTouchResizerClass = `${blockTouchResizerClass} top-1/2 -mt-1`
export const columnTouchResizerClass = `${blockTouchResizerClass} left-1/2 -ml-1`

export const tallDayCellBottomClass = 'min-h-3'
export const getShortDayCellBottomClass = (info: DayCellInfo) => cn(
  !info.isNarrow && 'min-h-0.5'
)

export const dayRowCommonClasses: CalendarOptions = {

  /* Day Row > List-Item Event
  ----------------------------------------------------------------------------------------------- */

  listItemEventClass: (info) => cn(
    'mb-px p-px rounded-sm',
    info.isNarrow ? 'mx-0.5' : 'mx-1',
    info.isSelected
      ? 'bg-foreground/5'
      : 'hover:bg-foreground/5',
  ),
  listItemEventInnerClass: (info) => cn(
    'flex flex-row items-center justify-between',
    info.isNarrow
      ? `py-px ${xxsTextClass}`
      : 'py-0.5 text-xs',
  ),
  listItemEventTimeClass: (info) => cn(
    info.isNarrow ? 'px-px' : 'px-0.5',
    'order-1 whitespace-nowrap overflow-hidden shrink-1',
  ),
  listItemEventTitleClass: (info) => cn(
    info.isNarrow ? 'px-px' : 'px-0.5',
    'font-medium whitespace-nowrap overflow-hidden shrink-100',
    info.timeText && 'text-ellipsis',
  ),

  /* Day Row > Row Event
  ----------------------------------------------------------------------------------------------- */

  rowEventClass: (info) => cn(
    info.isStart && (info.isNarrow ? 'ms-0.5' : 'ms-1'),
    info.isEnd && (info.isNarrow ? 'me-0.5' : 'me-1'),
  ),
  rowEventInnerClass: (info) => cn(info.isNarrow ? 'py-px' : 'py-0.5'),

  /* Day Row > More-Link
  ----------------------------------------------------------------------------------------------- */

  rowMoreLinkClass: (info) => cn(
    'mb-px border rounded-sm',
    info.isNarrow
      ? 'mx-0.5 border-primary hover:bg-foreground/5'
      : 'self-start mx-1 border-transparent bg-foreground/5 hover:bg-foreground/10',
  ),
  rowMoreLinkInnerClass: (info) => cn(
    info.isNarrow
      ? `p-px ${xxsTextClass}`
      : 'p-0.5 text-xs',
  ),
}
