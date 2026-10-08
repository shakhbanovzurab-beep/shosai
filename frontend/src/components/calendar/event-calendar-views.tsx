import FullCalendar, { type CalendarOptions } from '@fullcalendar/react'
import '@fullcalendar/react/skeleton.css'

import { dayOptions } from './event-calendar-day-options'
import { eventOptions } from './event-calendar-event-options'
import { layoutOptions } from './event-calendar-layout-options'
import { viewOptions } from './event-calendar-view-options'

export type EventCalendarViewProps =
  CalendarOptions &
  Required<Pick<CalendarOptions, 'popoverCloseContent'>> // ensure callers define icons

export function EventCalendarViews({
  height,
  views: userViews,
  ...restOptions
}: EventCalendarViewProps) {
  return (
    <FullCalendar
      height={height}
      {...eventOptions}
      {...dayOptions}
      {...layoutOptions}
      views={viewOptions(userViews)}
      {...restOptions}
    />
  )
}
